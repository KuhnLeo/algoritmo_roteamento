## Pré-requisitos
1 - Ambiente de rede já montado : 5 roteadores e 4 PCs rodando como containers Docker.
2 - Python 3 instalado.

## Como rodar
 
1 - Rode o algoritmo indicando o PC de origem e o de destino:
```
   sudo python3 life_routing.py --src pc0 --dst pc3 --manual --life 15 --test
```
 
   Parâmetros:
   - `--src` / `--dst`: PCs de origem e destino (`pc0`, `pc1`, `pc2`, `pc3`)
   - `--life`: vida inicial do pacote
   - `--manual`: usa pesos de latência pré-definidos no script (edite a
     constante `MANUAL_WEIGHTS` em `life_routing.py` para simular links
     bons/ruins). Sem essa flag, o script mede a latência real entre os
     roteadores com `ping`.
   - `--test`: depois de aplicar as rotas, faz um ping do PC de origem
     até o de destino para confirmar que a rota funcionou de ponta a ponta.
