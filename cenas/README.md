# 🎬 Pasta de Cenas (Fase 5 — manual)

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
