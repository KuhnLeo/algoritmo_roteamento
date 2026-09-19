# Como habilitar o OSPF em cada container através do terminal:

**1 - Habilitar a configuração do OSPF**

'docker exec router-a sed -i 's/ospfd=no/ospfd=yes/' /etc/frr/daemons'

'docker restart router-a router-b router-c router-d router-e'

Pode ser necessário rodar o start.sh novamente

**2 - 
