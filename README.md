# Configuração de rede via Linux e avaliação de algoritmos de roteamento
Trabalho para a matéria de Redes de Computadores: Internetworking, Roteamento e Transmissão

# Tracking
**1 - Efetuado instalação do Ubuntu 26.04.1 LTS via Virtual Box, atualizado pacotes pelo terminal e instalado docker e container lab e baixado a imagem do frrouting e alpine (imagem é mais leve que a do FRRouting, 13mb vs 230mb)**

'docker apt update'

'docker apt upgrade'

'docker pull alpine:latest /// frrouting/frr:latest'

Para conferir se as imagens instalaram normalmente: 'docker images'


**2 - Criado bridges para os switches:**

'sudo ip link add name switch0/switch1 type bridge $$ sudo ip link set switch0/switch1 up'


**3 - Setado os containers para configuração posterior**

'docker run -d --name router-a(b,c,d,e) --network none --cap-add=NET_ADMIN frrouting/frr:latest'

'docker run -d --name pc0(1,2,3) --network none --cap-add=NET_ADMIN alpine:latest sleep infinity'

Com 'docker ps -a' pode ser verificado os containers da VM

**4 - Renomeando os roteadores**

Para ler o PID do container: 'docker inspect -f '{{.State.Pid}}' router-a'

Para enxergar os namespaces do docker precisamos fazer 'sudo ln -sf /proc/$pid/ns/net /var/run/netns/router-a`


**5 - Criando os "cabos", par veth**

Cria um par de rede com os nomes veth-a1 e veth-pc0-1 -> 'sudo ip link add veth-a1(nome) type veth peer name veth-pc0-1'

Mover as pontas para os namespaces correspondentes -> 'sudo ip link set veth-a1 netns router-a'; 'sudo ip link set veth0pc0-1 netns pc0'
