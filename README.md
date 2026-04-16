# Google Calendar + Polybar

Integra Google Agenda no Polybar com:
- alerta de evento em 10 minutos;
- popup da agenda;
- calendário flutuante com coluna opcional da agenda (7 dias).

Dependências do sistema: `yad`, `notify-send`.

## Instalação

```bash
cd calendario-polybar
mkdir -p ~/.config/polybar/scripts
cp google_agenda_polybar.py ~/.config/polybar/scripts/
cp polybar-calendar-toggle.sh ~/.config/polybar/scripts/
chmod +x ~/.config/polybar/scripts/google_agenda_polybar.py ~/.config/polybar/scripts/polybar-calendar-toggle.sh
python -m venv ~/.config/polybar/scripts/.venv
~/.config/polybar/scripts/.venv/bin/pip install -r requirements.txt
```

## OAuth (cada usuário cria o seu)

1. Ative a **Google Calendar API** no seu projeto Google Cloud.
2. Crie credencial **OAuth Client ID** do tipo **Desktop app**.
3. Baixe e salve em: `~/.config/polybar/scripts/credentials.json`
4. Gere token local:

```bash
~/.config/polybar/scripts/.venv/bin/python ~/.config/polybar/scripts/google_agenda_polybar.py --mode print --no-browser
```

## Polybar

Use o bloco de `polybar-module.ini` no seu `~/.config/polybar/config.ini` e adicione `google-calendar` em `modules-center` ou `modules-right`.

## Cliques (módulo de data)

- esquerdo: abre/fecha calendário flutuante
- meio: mostra/oculta coluna da agenda (7 dias)
- direito: popup com agenda

## Sync e alerta

- consulta ao Google: a cada 30 min (`--cache-ttl 1800`)
- atualização no Polybar: a cada 60s
- janela de busca: 7 dias (`--days 7`) com eventos ilimitados (`--limit 0`)
- alerta: quando faltar até 10 min para o próximo evento com horário

## Segurança

Este repositório **não deve** conter:
- `credentials.json`
- `token.json`
- `.events_cache.json`
- `.notify_state.json`

Já estão no `.gitignore`.
