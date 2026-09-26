set -e

echo "==> Iniciando os containers e bridges"
docker start router-a router-b router-c router-d router-e pc0 pc1 pc2 pc3
sudo ip link add name switch0 type bridge
sudo ip link add name switch1 type bridge
sudo ip link set switch0 up
sudo ip link set switch1 up

echo "==> Reexpondo os namespaces de rede dos containers"
# Toda vez que reiniciar ele cria PIDs novos, assim ele pode nomear os namespaces sem problemas
sudo mkdir -p /var/run/netns
for c in router-a router-b router-c router-d router-e pc0 pc1 pc2 pc3; do
  pid=$(docker inspect -f '{{.State.Pid}}' "$c")
  sudo ln -sf /proc/"$pid"/ns/net /var/run/netns/"$c"
done

# Função que cria um par veth e move cada ponta para dentro do namespace do container correspondente, atribuindo IP e ativando a interface dos dois lados
connect() {
  local iface1=$1 ns1=$2 ip1=$3
  local iface2=$4 ns2=$5 ip2=$6

  sudo ip link add "$iface1" type veth peer name "$iface2"
  sudo ip link set "$iface1" netns "$ns1"
  sudo ip link set "$iface2" netns "$ns2"

  sudo ip netns exec "$ns1" ip addr add "$ip1" dev "$iface1"
  sudo ip netns exec "$ns1" ip link set "$iface1" up

  sudo ip netns exec "$ns2" ip addr add "$ip2" dev "$iface2"
  sudo ip netns exec "$ns2" ip link set "$iface2" up
}

# Função que cria um par veth onde uma ponta vai para dentro do roteador e a outra ponta fica na bridge do switch
connect_to_switch() {
  local iface=$1 ns=$2 ip=$3 bridge=$4 host_iface=$5

  sudo ip link add "$iface" type veth peer name "$host_iface"
  sudo ip link set "$iface" netns "$ns"

  sudo ip netns exec "$ns" ip addr add "$ip" dev "$iface"
  sudo ip netns exec "$ns" ip link set "$iface" up

  sudo ip link set "$host_iface" master "$bridge"
  sudo ip link set "$host_iface" up
}

# Chama as funções para definir as conexões dos roteadores
echo "==> Router A"
connect           veth-a1 router-a 192.168.0.1/24  veth-pc0 pc0      192.168.0.2/24 
connect_to_switch veth-a0 router-a 192.168.6.1/24 switch0 veth-a0-h
connect           veth-a2 router-a 192.168.4.1/24  veth-d2 router-d 192.168.4.2/24

echo "==> Router B"
connect           veth-b0 router-b 192.168.1.1/24  veth-pc1 pc1      192.168.1.2/24
connect_to_switch veth-b1 router-b 192.168.6.2/24 switch0 veth-b1-h
connect           veth-b2 router-b 192.168.5.1/24  veth-e1 router-e 192.168.5.2/24

echo "==> Router C"
connect_to_switch veth-c1 router-c 192.168.6.3/24 switch0 veth-c1-h
connect_to_switch veth-c0 router-c 192.168.7.1/24 switch1 veth-c0-h

echo "==> Router D"
connect           veth-d0 router-d 192.168.2.1/24  veth-pc2 pc2      192.168.2.2/24
connect_to_switch veth-d1 router-d 192.168.7.2/24 switch1 veth-d1-h

echo "==> Router E"
connect           veth-e0 router-e 192.168.3.1/24  veth-pc3 pc3      192.168.3.2/24
connect_to_switch veth-e2 router-e 192.168.7.3/24 switch1 veth-e2-h

# Para os roteadores poderem transmitir os pacotes
echo "==> Habilitando IP forwarding nos roteadores"
for r in router-a router-b router-c router-d router-e; do
  sudo ip netns exec "$r" sysctl -w net.ipv4.ip_forward=1 >/dev/null
done

echo "==> Configurando gateways"
sudo ip netns exec pc0 ip route add default via 192.168.0.1
sudo ip netns exec pc1 ip route add default via 192.168.1.1
sudo ip netns exec pc2 ip route add default via 192.168.2.1
sudo ip netns exec pc3 ip route add default via 192.168.3.1

echo ""
echo "==> Pronto seu tonto"
