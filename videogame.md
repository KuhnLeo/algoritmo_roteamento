# Algoritmo próprio de roteamento (videogame_algoritmo.py)
 
Cada roteador roda uma cópia do script `videogame_algoritmo.py`. Elas trocam
informação entre vizinhos por UDP e cada roteador instala as próprias rotas.
 
## Passo a passo
 
**1. Subir a rede**:
 
```
sudo ./start.sh
```
 
Se rodar o `start.sh` uma segunda vez sem reiniciar a VM, apague as bridges antes:
 
```
sudo ip link delete switch0
sudo ip link delete switch1
```
 
**2. Copiar o script para dentro dos 5 roteadores:**
 
```
for r in router-a router-b router-c router-d router-e; do
  docker cp videogame_algoritmo.py $r:/videogame_algoritmo.py
done
```
 
**3. Iniciar o algoritmo em cada roteador:**
 
```
for r in router-a router-b router-c router-d router-e; do
  docker exec -d $r sh -c "python3 /videogame_algoritmo.py --router $r --life 15 > /tmp/life.log 2>&1"
done
```
 
- `--life`: vida máxima (custo acumulado a partir do qual a rota é descartada). Precisa ser o **mesmo valor nos 5 roteadores**.
- Sem `--manual`: mede a latência real com ping (usar nos testes).
- Com `--manual`: usa os pesos fixos que estão dentro do script (usar só para demonstrar).

