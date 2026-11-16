# Internacionalização (i18n)

Contrato comum: `docs/03-arquitetura-i18n-kde.md` do repositório de documentação
do Mainuan. Resumo do que vale aqui:

| Item | Valor |
|---|---|
| API | `gettext` da biblioteca padrão (`src/mainuan_recursos/i18n.py`: `_`, `ngettext`, `pgettext`, `N_`) |
| Domínio | `mainuan-atualizador-recursos` (nome do pacote Debian) |
| Idioma-fonte | inglês (msgid); a interface brasileira está em `po/pt_BR.po` |
| Catálogo instalado | `/usr/share/locale/<idioma>/LC_MESSAGES/mainuan-atualizador-recursos.mo` |
| Botões padrão do Qt | `qtbase_<idioma>.qm` para `QLocale.system()` (`localization.install_translations`) |

O idioma vem da sessão (`LANGUAGE`, `LC_ALL`, `LC_MESSAGES`, `LANG`). O aplicativo
nunca força idioma; idioma sem catálogo mostra inglês.

## Layout

```
po/
  i18n.sh                         script padrão Mainuan (não editar localmente)
  i18n.conf                       domínio e metadados
  POTFILES.in                     arquivos extraídos (.py e modelos .desktop.in)
  LINGUAS                         idiomas instalados (hoje: pt_BR)
  mainuan-atualizador-recursos.pot
  pt_BR.po
data/*.desktop.in                 modelos em inglês; o build gera os .desktop traduzidos
```

## Tarefas

```bash
po/i18n.sh extract        # regenera o POT depois de mudar strings
po/i18n.sh update         # mescla o POT em todos os .po do LINGUAS
po/i18n.sh validate       # msgfmt --check + placeholders (portão de CI)
po/i18n.sh check-pot      # falha se o POT versionado estiver desatualizado (CI)
po/i18n.sh coverage       # estatística por idioma
po/i18n.sh add <idioma>   # novo catálogo com Plural-Forms verificado
```

Rodar do código-fonte em outro idioma:

```bash
po/i18n.sh compile build/locale          # i18n.py procura build/locale no checkout
LANGUAGE=pt_BR PYTHONPATH=src python3 -m mainuan_recursos --demo
LANGUAGE=en    PYTHONPATH=src python3 -m mainuan_recursos --demo
# ou aponte para qualquer pasta: MAINUAN_RECURSOS_LOCALEDIR=/caminho/locale
```

Testes: `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -m unittest discover -s tests`.
`tests/i18n_support.py` compila `po/*.po` (requer `msgfmt`) e roda a suíte com
`LANGUAGE=pt_BR`, pois a maioria dos testes confere o texto brasileiro original.
`tests/test_localization.py` executa o código real em processos separados com
`LANGUAGE=pt_BR`, `LANGUAGE=en`, `LC_ALL=C` e idioma desconhecido, e gera os
`.desktop` com `msgfmt --desktop`.

## Empacotamento

`tools/stage-package.sh` (usado por `debian/rules` e `build-package.sh`):

* `po/i18n.sh compile "$DEST/usr/share/locale"` — instala os `.mo`;
* `msgfmt --desktop --template=data/X.desktop.in -d po` — gera
  `/usr/share/applications/org.mainuan.Recursos.desktop` e
  `/etc/xdg/autostart/mainuan-recursos.desktop` (nomes instalados inalterados).

`gettext` é dependência de build (`debian/control`). Em execução nada novo é
necessário além de `qt6-translations-l10n`, já declarado.

## Regras práticas

* Frases completas com placeholders nomeados: `_('Could not open the history: {error}').format(error=exc)`.
* Rótulos curtos ambíguos usam contexto: `pgettext('package status', 'Install')`.
* Situações de pacote: `packages.INSTALL`/`UPGRADE`/`RECEIVED` são códigos
  internos usados pela lógica; a interface mostra `packages.status_text(status)`.
  Situações bloqueantes já são texto traduzido.
* Não traduzir: nomes de pacote/repositório, URLs, caminhos, `packages.txt`/`message.txt`,
  saída bruta do APT/PackageKit (`deb._failure_string`, `ErrorCode`), argumentos de
  linha de comando e nomes de cenário (`--scenario novo`).
* Mensagens de erro de validação (catálogo, canal GitHub, homologação) chegam ao
  usuário na barra de situação e por isso são traduzidas; identificadores técnicos
  vão em placeholders.

## Particularidades

* **Conteúdo remoto não passa pelo gettext.** Título, resumo e títulos de recursos
  vêm do catálogo assinado (`catalogo/novidades.json`, `examples/catalog.json`) ou
  de `message.txt`/nome da release no canal GitHub; são conteúdo editorial e
  aparecem como publicados. O esquema 1 do catálogo rejeita campos desconhecidos
  (`fields()` em `catalog.py`), então não há hoje como publicar variantes por
  idioma; isso exige uma versão nova do esquema (por exemplo `title`/`summary`
  como objetos `{"en": …, "pt_BR": …}` com escolha pelo idioma da sessão) e uma
  decisão editorial. `data/atualizador-recursos.json` é configuração, sem texto
  de interface.
* O título gerado das edições do canal GitHub ("Mainuan has news!") é texto do
  aplicativo: é traduzido ao exibir, mesmo quando vem do cache local.
* O PackageKit recebe a dica `locale=` da sessão (`LC_ALL`/`LC_MESSAGES`/`LANG`),
  não mais `pt_BR.UTF-8` fixo.
* A página de manual (`data/man/*.1`) continua só em português; traduzi-la exige
  po4a ou equivalente.
* As ferramentas de desenvolvimento em `tools/` (publicação, homologação, prévia)
  não são instaladas e não foram internacionalizadas.
