# 🎬 Pasta de Cenas (Fase 5)

## Modo automático: `gerar_cenas.py` (grátis, sem cadastro)
Com o `roteiro.json` baixado do site na raiz do projeto, rode:

```
python gerar_cenas.py
```

As imagens nascem sozinhas aqui (`cena1.jpg`, `cena2.jpg`...) a partir do
`prompt_visual` de cada cena — API keyless do Pollinations (R$ 0, ilimitado
na prática; o script espera os ~45s de ritmo entre imagens sozinho).
Imagens antigas da mesma cena são substituídas na hora — nada de backup
acumulando. A marca d'água da API some no recorte 9:16 que o render faz.

**Mesclando com cenas manuais:** se você quiser um vídeo baixado (ou
qualquer cena sua) no lugar de uma imagem automática, é só colocar o
arquivo como `cenaN.mp4` na pasta — o render **prefere o vídeo** quando
a mesma cena tem os dois.

## Modo manual (opcional)
Coloque aqui os arquivos de **cada cena** que você gerou manualmente.

## Como nomear
Use um número no nome do arquivo — é ele que define a ordem:

```
cena1.mp4
cena2.mp4
cena3.mp4
...
cena10.mp4
```

Também funcionam: `01_cena.mp4`, `cena_02.png`, `2-cena.webp`...
(qualquer número no nome; `cena2` vem antes de `cena10`)

## Formatos aceitos
- 🎥 Vídeos: `.mp4` `.mov` `.avi` `.mkv` `.webm`
- 🖼️ Imagens: `.png` `.jpg` `.jpeg` `.webp` (ficam **3 segundos** na tela —
  edite `TEMPO_IMAGEM_SEGUNDOS` no `render_video.py` se quiser mudar)

## Dica
Gere todas as cenas no **mesmo tamanho** (ex.: 1080x1920 para Shorts) —
assunto o vídeo final fica sem bordas pretas.

## Depois é só rodar
```
python render_video.py
```
O vídeo final sai na pasta `output/`.
