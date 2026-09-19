# Como habilitar o RIP em cada container através do terminal:

**1 - Ativar o RIPv2 no arquivo de configuração**

Para cada roteador rode 'docker exec -it router-a sed -i 's/ripd=no/ripd=yes/' /etc/frr/daemons'

Depois precisamos reiniciar cada container

'docker restart router-a'

**2 - Configurando o RIP**

Precisamos entrar na área de configuração específica, para isso rode

'docker exec -it router-a vtysh'

configure terminal

router rip

version 2

netwrok subredesIPv4/24

exit

exit

write memory

Talvez seja necessário rodar o start.sh novamente. Se estiver tudo OK vai rodar sem problemas

**Testes:**

docker exec pc1 ping -c 3 192.168.2.2

docker exec pc2 ping -c 3 192.168.1.2

docker exec pc3 ping -c 3 192.168.0.2
