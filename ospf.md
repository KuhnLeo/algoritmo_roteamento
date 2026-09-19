# Como habilitar o OSPF em cada container através do terminal:

**1 - Habilitar a configuração do OSPF**

'docker exec router-a sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/daemons'

'docker restart router-a router-b router-c router-d router-e'

Pode ser necessário rodar o start.sh novamente

**2 - Configurando o OSPF**

'docker exec -it router-a vtysh'

configure terminal

router ospf

network <subredeIPv4>/24 area 0

exit

exit

write memory

**3 - Testes:**

docker exec pc1 ping -c 3 192.168.2.2

docker exec pc2 ping -c 3 192.168.1.2

docker exec pc3 ping -c 3 192.168.0.2
