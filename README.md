# Configuração de rede via Linux e avaliação de algoritmos de roteamento
Trabalho para a matéria de Redes de Computadores: Internetworking, Roteamento e Transmissão

# Tracking
1 - Efetuado instalação do Ubuntu 22.04 via Virtual Box, atualizado pacotes pelo terminal e instalado docker e container lab e baixado a imagem do frrouting

2 - Criado bridges para os switches:
sudo ip link add name switch0/switch1 type bridge $$ sudo ip link set switch0/switch1 up

3 - Baixado a imagem do linux Alpine (é mais leve que a imagem do FRRouting, 13mb vs 230mb)
docker pull alpine:latest

4 - Setado os containers para configuração posterior
docker run -d --name router-a(b,c,d,e) --network none --cap-add=NET_ADMIN frrouting/frr:latest
docker run -d --name pc0 --network none --cap-add=NET_ADMIN alpine:latest sleep infinity
