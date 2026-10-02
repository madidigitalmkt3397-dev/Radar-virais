# 🔊 Banco de Efeitos Sonoros

Pasta dos efeitos **grátis** da **Fase 8** do render.

## Como funciona (automático)

- **Whoosh na troca de cena**: o render gera sozinho, sem arquivo nenhum.
- **`efeito_sonoro_sugerido`** de cada cena: o render procura AQUI um
  arquivo que combine com a sugestão (ex.: sugestão `aplausos` →
  `aplausos.mp3`). Se não achar, ele **sintetiza na hora** estes:
  `whoosh`, `suspense`, `heartbeat`, `ding` e `impacto`.
  Só o que não dá para sintetizar (risadas, aplausos, música...)
  precisa de arquivo — e o render avisa qual está faltando.

## Regras de nome

- Salve com o mesmo nome da sugestão, em minúsculas:
  `aplausos.mp3`, `risada.wav`, `suspense.mp3`
- Extensões aceitas: `.mp3` `.wav` `.ogg` `.m4a` `.aac` `.flac`
- `swoosh.wav` ou `transicao.wav`: usado no lugar do whoosh automático
  das trocas (se existir, tem prioridade)

## Onde baixar grátis

- Biblioteca de áudio do YouTube (studio.youtube.com → Áudio livre)
- pixabay.com/pt/sound-effects
- freesound.org (conta grátis)

Depois de baixar: salve aqui e rode `python render_video.py` de novo.

## Chaves de ligar/desligar (render_video.py)

- `SFX_LIGADO` — liga/desliga todos os efeitos
- `SFX_SO_ARQUIVOS` — `True` = **só** toca o que estiver nesta pasta
  (nunca sintetiza; sem arquivo = silêncio)
- `SFX_TRANSICAO` — whoosh nas trocas
- `SFX_POR_CENA` — efeito sugerido no roteiro
- `SFX_VOLUME` / `SFX_VOLUME_TRANSICAO` — volume (0.0 a 1.0)
