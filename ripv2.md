# Como habilitar o RIP em cada container através do terminal:

**1 - Ativar o RIPv2 no arquivo de configuração**

Para cada roteador rode 'docker exec -it router-a sed -i 's/ripd=no/ripd=yes/' /etc/frr/daemons'

Depois precisamos reiniciar cada container

'docker restart router-a router-b router-c router-d router-e'

**2 - Configurando o RIP**

Precisamos entrar na área de configuração específica, para isso rode

'docker exec -it router-a vtysh'

configure terminal

router rip

version 2

network "subredeIPv4"/24

exit

exit

write memory

Possivelmente algum dos comandos vão retornar algo como "% Can't open configuration ou % Unknown comand, mas é só ignorar.
Talvez seja necessário rodar o start.sh novamente. Se estiver tudo OK vai rodar sem problemas

**3 - Testes:**

docker exec pc1 ping -c 3 192.168.2.2

docker exec pc2 ping -c 3 192.168.1.2

docker exec pc3 ping -c 3 192.168.0.2

**4 - Desligando o RIPv2>**

'docker exec router-a vtysh -c "configure terminal" -c "no router rip" -c "write memory"'

Para ver se deu certo é só fazer:

'docker exec router-a vtysh -c "show running-config"

'docker exec router-a vtysh -c "show ip route rip"
