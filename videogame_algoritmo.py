#!/usr/bin/env python3
"""
Videogame Algoritmo
======================================================================

Roda DENTRO de cada roteador (em segundo plano), do mesmo jeito que o
ripd/ospfd do FRR fazem. Cada instância:

1. Conhece só seus vizinhos diretos e as redes diretamente conectadas
   a ele.
2. Mede (ou usa peso manual para) a latência até cada vizinho.
3. Troca periodicamente, via UDP, um "vetor de distâncias" com os
   vizinhos: quais redes conhece e com que custo acumulado (latência).
4. Ao receber o vetor de um vizinho, recalcula: custo_total = custo do
   link até o vizinho + custo que o vizinho reporta. Se esse total
   alcançar a "vida máxima" (LIFE_MAX), a rota é descartada -- é a
   mesma ideia de "a vida chegou a zero, abandona esse caminho" da
   versão centralizada, só que aplicada de forma incremental e
   distribuída (parecido com o "count to infinity" do RIP, só que
   usando latência acumulada em vez de contagem de saltos).
5. Aplica a melhor rota conhecida pra cada rede via `ip route replace`,
   diretamente no namespace do próprio roteador (o script já roda
   dentro dele).

Uso (dentro do container do roteador):
    python3 life_routing_daemon.py --router router-a --life 15
    python3 life_routing_daemon.py --router router-a --life 15 --manual
"""

import argparse
import json
import re
import socket
import subprocess
import threading
import time

PORT = 5000
INTERVAL = 5  # segundos entre trocas de vetor

# ---------------------------------------------------------------------
# Topologia
# ---------------------------------------------------------------------

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

LOCAL_NETS = {
    "router-a": ["192.168.0.0/24"],
    "router-b": ["192.168.1.0/24"],
    "router-c": [],
    "router-d": ["192.168.2.0/24"],
    "router-e": ["192.168.3.0/24"],
}

# Pesos manuais (ms), usados com --manual. Mesmos valores da versão
# centralizada, pra ficar comparável.
MANUAL_WEIGHTS = {
    ("router-a", "router-b"): 5,
    ("router-a", "router-c"): 8,
    ("router-b", "router-c"): 3,
    ("router-c", "router-d"): 4,
    ("router-c", "router-e"): 20,
    ("router-d", "router-e"): 6,
    ("router-a", "router-d"): 15,
    ("router-b", "router-e"): 7,
}

RTT_RE = re.compile(r"= [\d.]+/([\d.]+)/")


def neighbors_of(router):
    """Retorna {vizinho: (meu_ip_no_link, ip_do_vizinho)} para um roteador."""
    result = {}
    for (r1, r2), (ip1, ip2) in LINKS.items():
        if router == r1:
            result[r2] = (ip1, ip2)
        elif router == r2:
            result[r1] = (ip2, ip1)
    return result


def link_weight(r1, r2):
    key = (r1, r2) if (r1, r2) in MANUAL_WEIGHTS else (r2, r1)
    return MANUAL_WEIGHTS[key]


def measure_latency_ms(target_ip, count=1, timeout=1):
    result = subprocess.run(
        ["ping", "-c", str(count), "-W", str(timeout), target_ip],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    match = RTT_RE.search(result.stdout)
    return float(match.group(1)) if match else None


class LifeRoutingDaemon:
    def __init__(self, router, life_max, use_manual):
        self.router = router
        self.life_max = life_max
        self.use_manual = use_manual
        self.neighbors = neighbors_of(router)  # nome -> (meu_ip, ip_vizinho)
        self.vector = {net: 0.0 for net in LOCAL_NETS[router]}
        self.next_hop = {net: None for net in LOCAL_NETS[router]}
        self.neighbor_vectors = {}  # nome_vizinho -> {net: custo}
        self.lock = threading.Lock()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("0.0.0.0", PORT))

    def log(self, msg):
        print(f"[{self.router}] {msg}", flush=True)

    def link_cost_to(self, neighbor):
        if self.use_manual:
            return link_weight(self.router, neighbor)
        _, neighbor_ip = self.neighbors[neighbor]
        return measure_latency_ms(neighbor_ip)

    def recompute_vector(self):
        """Recalcula o vetor de distâncias a partir dos vetores recebidos
        dos vizinhos (Bellman-Ford com corte em life_max)."""
        with self.lock:
            new_vector = {net: 0.0 for net in LOCAL_NETS[self.router]}
            new_next_hop = {net: None for net in LOCAL_NETS[self.router]}

            for neighbor, their_vector in self.neighbor_vectors.items():
                cost_to_neighbor = self.link_cost_to(neighbor)
                if cost_to_neighbor is None:
                    continue  # vizinho parece fora do ar
                for net, cost in their_vector.items():
                    total = cost_to_neighbor + cost
                    if total >= self.life_max:
                        continue  # a vida chegaria a zero, abandona essa rota
                    if net not in new_vector or total < new_vector[net]:
                        new_vector[net] = total
                        new_next_hop[net] = neighbor

            mudou = new_vector != self.vector
            self.vector = new_vector
            self.next_hop = new_next_hop

        if mudou:
            self.apply_routes()

    def apply_routes(self):
        for net, next_hop_router in self.next_hop.items():
            if next_hop_router is None:
                continue  # rede local, já está diretamente conectada
            _, neighbor_ip = self.neighbors[next_hop_router]
            subprocess.run(["ip", "route", "replace", net, "via", neighbor_ip])
            self.log(f"rota {net} via {next_hop_router} ({neighbor_ip}) "
                     f"custo={self.vector[net]:.2f}")

    def send_vector_to(self, neighbor):
        _, neighbor_ip = self.neighbors[neighbor]
        with self.lock:
            # split horizon: não anuncia de volta pro vizinho de quem
            # aprendeu a rota (evita loop trivial de 2 nós)
            payload = {
                net: cost for net, cost in self.vector.items()
                if self.next_hop.get(net) != neighbor
            }
        message = json.dumps({"router": self.router, "vector": payload}).encode()
        try:
            self.sock.sendto(message, (neighbor_ip, PORT))
        except OSError as e:
            self.log(f"erro ao enviar pra {neighbor}: {e}")

    def sender_loop(self):
        while True:
            for neighbor in self.neighbors:
                self.send_vector_to(neighbor)
            time.sleep(INTERVAL)

    def receiver_loop(self):
        while True:
            data, _ = self.sock.recvfrom(65535)
            try:
                msg = json.loads(data.decode())
            except (ValueError, UnicodeDecodeError):
                continue
            neighbor = msg.get("router")
            vector = msg.get("vector")
            if neighbor not in self.neighbors or not isinstance(vector, dict):
                continue
            with self.lock:
                self.neighbor_vectors[neighbor] = vector
            self.recompute_vector()

    def run(self):
        self.log(f"iniciado. vizinhos: {list(self.neighbors)}. "
                  f"redes locais: {LOCAL_NETS[self.router]}. life_max={self.life_max}")
        threading.Thread(target=self.receiver_loop, daemon=True).start()
        self.sender_loop()  # roda no thread principal


def main():
    parser = argparse.ArgumentParser(description="Life Routing Daemon")
    parser.add_argument("--router", required=True, choices=LOCAL_NETS.keys())
    parser.add_argument("--life", type=float, default=15.0)
    parser.add_argument("--manual", action="store_true")
    args = parser.parse_args()

    daemon = LifeRoutingDaemon(args.router, args.life, args.manual)
    daemon.run()


if __name__ == "__main__":
    main()
