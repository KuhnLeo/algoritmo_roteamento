#!/usr/bin/env python3
"""
Algoritmo próprio de roteamento - "Life Routing"
=================================================

Ideia: cada pacote começa com uma "barra de vida" cheia. A cada roteador
(hop) que ele atravessa, perde vida proporcionalmente à latência daquele
link. Se a vida chegar a zero antes de alcançar o destino, o caminho é
abandonado (backtrack) e o algoritmo tenta outro. No final, escolhe o
caminho que consegue chegar ao destino perdendo a MENOR quantidade de
vida possível (ou seja, o de menor latência acumulada).

Diferenças em relação ao RIP/OSPF:
- RIP nunca "desiste" de um caminho ruim; aqui o algoritmo pode recusar
  caminhos tecnicamente válidos por serem ruins demais.
- É centralizado (roda uma vez, fora dos roteadores) em vez de
  distribuído (troca de mensagens periódica entre vizinhos).
- Usa latência real medida como custo, não hop count fixo.

Como usar:
    sudo python3 life_routing.py --src pc0 --dst pc3
    sudo python3 life_routing.py --src pc0 --dst pc3 --life 50 --manual
    sudo python3 life_routing.py --src pc0 --dst pc3 --test

Precisa rodar como root (ou com sudo) porque usa `ip netns exec`.
"""

import argparse
import re
import subprocess
import sys

# ---------------------------------------------------------------------------
# Topologia (baseada no start.sh da dupla)
# ---------------------------------------------------------------------------

# Cada link direto entre dois roteadores e os IPs de cada lado.
# Os pares (router-a, router-b, router-c) e (router-c, router-d, router-e)
# estão no mesmo segmento (switch0 / switch1), então qualquer par dentro
# do mesmo switch enxerga o outro diretamente (mesma sub-rede).
LINKS = {
    ("router-a", "router-b"): ("192.168.6.1", "192.168.6.2"),
    ("router-a", "router-c"): ("192.168.6.1", "192.168.6.3"),
    ("router-b", "router-c"): ("192.168.6.2", "192.168.6.3"),
    ("router-c", "router-d"): ("192.168.7.1", "192.168.7.2"),
    ("router-c", "router-e"): ("192.168.7.1", "192.168.7.3"),
    ("router-d", "router-e"): ("192.168.7.2", "192.168.7.3"),
    ("router-a", "router-d"): ("192.168.4.1", "192.168.4.2"),
    ("router-b", "router-e"): ("192.168.5.1", "192.168.5.2"),
}

# Rede e IP de teste de cada PC, e qual roteador é o gateway dele.
PCS = {
    "pc0": {"gateway": "router-a", "net": "192.168.0.0/24", "ip": "192.168.0.2"},
    "pc1": {"gateway": "router-b", "net": "192.168.1.0/24", "ip": "192.168.1.2"},
    "pc2": {"gateway": "router-d", "net": "192.168.2.0/24", "ip": "192.168.2.2"},
    "pc3": {"gateway": "router-e", "net": "192.168.3.0/24", "ip": "192.168.3.2"},
}

# Pesos manuais (ms) usados quando --manual é passado, já que numa rede toda
# local a latência real medida por ping fica perto de 0 e não gera uma
# demonstração interessante do backtracking. Ajuste esses valores à vontade
# pra simular links "ruins" (ex: usando `tc qdisc add ... netem delay`).
MANUAL_WEIGHTS = {
    ("router-a", "router-b"): 5,
    ("router-a", "router-c"): 8,
    ("router-b", "router-c"): 3,
    ("router-c", "router-d"): 4,
    ("router-c", "router-e"): 20,   # link "ruim" de propósito, pra forçar backtrack
    ("router-d", "router-e"): 6,
    ("router-a", "router-d"): 15,
    ("router-b", "router-e"): 7,
}

RTT_RE = re.compile(r"= [\d.]+/([\d.]+)/")


def neighbor_ip(link_key, from_router, to_router):
    ip1, ip2 = LINKS[link_key]
    return ip2 if link_key[0] == from_router else ip1


def build_neighbor_ip_table():
    table = {}
    for (r1, r2), (ip1, ip2) in LINKS.items():
        table[(r1, r2)] = ip2
        table[(r2, r1)] = ip1
    return table


NEIGHBOR_IP = build_neighbor_ip_table()


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def measure_latency_ms(from_router, target_ip, count=3, timeout=1):
    """Faz ping de dentro do namespace de from_router até target_ip e
    retorna a latência média em ms, ou None se falhar."""
    cmd = ["sudo", "ip", "netns", "exec", from_router,
           "ping", "-c", str(count), "-W", str(timeout), target_ip]
    result = run(cmd)
    if result.returncode != 0:
        return None
    match = RTT_RE.search(result.stdout)
    if not match:
        return None
    return float(match.group(1))


def build_graph(use_manual=False, verbose=True):
    """Monta o grafo ponderado. Cada aresta é o custo (ms) do link."""
    graph = {}

    def add_edge(a, b, weight):
        graph.setdefault(a, {})[b] = weight
        graph.setdefault(b, {})[a] = weight

    for (r1, r2), (ip1, ip2) in LINKS.items():
        if use_manual:
            weight = MANUAL_WEIGHTS[(r1, r2)]
            if verbose:
                print(f"  [manual] {r1} <-> {r2}: {weight} ms")
        else:
            lat_ab = measure_latency_ms(r1, ip2)
            lat_ba = measure_latency_ms(r2, ip1)
            samples = [x for x in (lat_ab, lat_ba) if x is not None]
            if not samples:
                if verbose:
                    print(f"  [!] {r1} <-> {r2}: link parece fora do ar, ignorando")
                continue
            weight = sum(samples) / len(samples)
            if verbose:
                print(f"  [medido] {r1} <-> {r2}: {weight:.3f} ms")
        add_edge(r1, r2, weight)

    return graph


# ---------------------------------------------------------------------------
# Busca com barra de vida (DFS com poda + backtracking)
# ---------------------------------------------------------------------------

def find_path_with_life(graph, src, dst, life_inicial, verbose=True):
    """Explora todos os caminhos simples de src até dst, gastando vida a
    cada hop. Caminhos que zeram a vida são abandonados. No final, retorna
    o caminho que chega ao destino com a MAIOR vida restante (= menor
    custo acumulado)."""

    melhores = []  # lista de (caminho, vida_restante, custo_total)

    def dfs(atual, visitados, caminho, vida, custo_acumulado, profundidade):
        indent = "  " * profundidade
        if atual == dst:
            if verbose:
                print(f"{indent}chegou no destino {dst} com vida restante = {vida:.2f}")
            melhores.append((list(caminho), vida, custo_acumulado))
            return

        for vizinho, custo in graph.get(atual, {}).items():
            if vizinho in visitados:
                continue
            nova_vida = vida - custo
            if verbose:
                print(f"{indent}tentando {atual} -> {vizinho} "
                      f"(custo {custo:.2f}, vida ficaria em {nova_vida:.2f})")
            if nova_vida <= 0:
                if verbose:
                    print(f"{indent}  vida chegou a zero, abandonando esse caminho (backtrack)")
                continue
            visitados.add(vizinho)
            caminho.append(vizinho)
            dfs(vizinho, visitados, caminho, nova_vida, custo_acumulado + custo, profundidade + 1)
            caminho.pop()
            visitados.remove(vizinho)

    dfs(src, {src}, [src], life_inicial, 0.0, 0)

    if not melhores:
        return None, None, None

    # escolhe o caminho com maior vida restante (= menor custo total)
    melhores.sort(key=lambda x: x[2])
    return melhores[0]


# ---------------------------------------------------------------------------
# Aplicação das rotas
# ---------------------------------------------------------------------------

def apply_routes(path, src_net, dst_net, verbose=True):
    """Instala rotas estáticas nos roteadores do caminho escolhido, nas
    duas direções (ida até dst_net, volta até src_net)."""

    # ida: cada roteador do caminho (exceto o último) precisa saber
    # chegar em dst_net através do próximo salto
    for i in range(len(path) - 1):
        router = path[i]
        next_hop = NEIGHBOR_IP[(router, path[i + 1])]
        cmd = ["sudo", "ip", "netns", "exec", router,
               "ip", "route", "replace", dst_net, "via", next_hop]
        if verbose:
            print(f"  {router}: rota para {dst_net} via {next_hop}")
        run(cmd)

    # volta: cada roteador do caminho (exceto o primeiro) precisa saber
    # voltar pra src_net através do salto anterior
    for i in range(len(path) - 1, 0, -1):
        router = path[i]
        prev_hop = NEIGHBOR_IP[(router, path[i - 1])]
        cmd = ["sudo", "ip", "netns", "exec", router,
               "ip", "route", "replace", src_net, "via", prev_hop]
        if verbose:
            print(f"  {router}: rota para {src_net} via {prev_hop}")
        run(cmd)


def test_connectivity(src_pc, dst_pc, count=4):
    dst_ip = PCS[dst_pc]["ip"]
    cmd = ["sudo", "ip", "netns", "exec", src_pc, "ping", "-c", str(count), dst_ip]
    print(f"\n$ ping de {src_pc} para {dst_pc} ({dst_ip})")
    result = run(cmd)
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Life Routing - algoritmo próprio de roteamento")
    parser.add_argument("--src", required=True, choices=PCS.keys(), help="PC de origem (ex: pc0)")
    parser.add_argument("--dst", required=True, choices=PCS.keys(), help="PC de destino (ex: pc3)")
    parser.add_argument("--life", type=float, default=100.0, help="Vida inicial do pacote")
    parser.add_argument("--manual", action="store_true",
                         help="Usar pesos manuais em vez de medir latência real com ping")
    parser.add_argument("--test", action="store_true",
                         help="Testar conectividade fim a fim depois de aplicar as rotas")
    args = parser.parse_args()

    if args.src == args.dst:
        sys.exit("Origem e destino não podem ser o mesmo PC.")

    src_router = PCS[args.src]["gateway"]
    dst_router = PCS[args.dst]["gateway"]
    src_net = PCS[args.src]["net"]
    dst_net = PCS[args.dst]["net"]

    print(f"=== Life Routing: {args.src} ({src_router}) -> {args.dst} ({dst_router}) ===\n")

    print("Medindo custos dos links...")
    graph = build_graph(use_manual=args.manual)

    if src_router == dst_router:
        print("\nOrigem e destino estão no mesmo roteador, nenhuma rota extra necessária.")
        return

    print(f"\nBuscando caminho com vida inicial = {args.life}...")
    caminho, vida_restante, custo_total = find_path_with_life(graph, src_router, dst_router, args.life)

    if caminho is None:
        print("\nNenhum caminho sobrevive com essa vida inicial. "
              "Tente aumentar --life ou revisar os pesos dos links.")
        return

    print(f"\n=> Melhor caminho encontrado: {' -> '.join(caminho)}")
    print(f"=> Custo total (latência acumulada): {custo_total:.2f} ms")
    print(f"=> Vida restante ao chegar: {vida_restante:.2f}")

    print("\nAplicando rotas...")
    apply_routes(caminho, src_net, dst_net)

    if args.test:
        test_connectivity(args.src, args.dst)


if __name__ == "__main__":
    main()
