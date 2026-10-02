# 🔊 Banco de Efeitos Sonoros

Pasta dos efeitos **grátis** da **Fase 8** do render.

## Padrão: só toca o que estiver nesta pasta

Com `SFX_SO_ARQUIVOS = True` (**padrão**), **nada é inventado**: se o
arquivo não estiver aqui, aquela cena ou troca fica em **silêncio**
e o render lista o que faltou.

## Modo automático (opcional)

Com `SFX_SO_ARQUIVOS = False`, quem não achar arquivo o render
**sintetiza na hora**: `whoosh`, `suspense`, `heartbeat`, `ding`,
`impacto` — e o whoosh das trocas nasce sozinho, sem arquivo.

## Regras de nome

- Salve com o mesmo nome da sugestão, em minúsculas:
  `aplausos.mp3`, `risada.wav`, `suspense.mp3`
- Extensões aceitas: `.mp3` `.wav` `.ogg` `.m4a` `.aac` `.flac`
- `swoosh.wav` ou `transicao.wav`: é o som das **trocas de cena** (no
  modo automático ele substitui o whoosh gerado)

## Onde baixar grátis

- Biblioteca de áudio do YouTube (studio.youtube.com → Áudio livre)
- pixabay.com/pt/sound-effects
- freesound.org (conta grátis)

Depois de baixar: salve aqui e rode `python render_video.py` de novo.

## Chaves de ligar/desligar (render_video.py)

- `SFX_LIGADO` — liga/desliga todos os efeitos
- `SFX_SO_ARQUIVOS` — **padrão `True`** = só toca o que estiver nesta
  pasta (nunca sintetiza; sem arquivo = silêncio). `False` = modo automático
- `SFX_TRANSICAO` — whoosh nas trocas
- `SFX_POR_CENA` — efeito sugerido no roteiro
- `SFX_VOLUME` / `SFX_VOLUME_TRANSICAO` — volume (0.0 a 1.0)
