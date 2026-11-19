# Publicar um anúncio de novidades

A partir da versão 0.4.0, a janela **"Olá! O Mainuan tem novidades"** só abre
sozinha quando a equipe publica um anúncio **de propósito** no arquivo
[`announcements.json`](../announcements.json), na `main` deste repositório.
Releases dos programas, `packages.txt` e `message.txt` **não** são anúncios.

Sem anúncio ativo, a verificação do login consulta em silêncio e encerra: sem
janela, sem notificação, sem ícone na bandeja e sem roubar o foco.

## Publicar (pelo navegador, sem comandos)

1. Abra `announcements.json` no GitHub e clique no lápis (**Edit this file**).
2. Preencha:
   - `"enabled": true`
   - `"id"`: nome curto e fixo do anúncio, em minúsculas, números e hífen
     (ex.: `"gestao-drivers-1-1"`).
   - `"version"`: comece com `1`.
   - `"title"` e `"message"`: textos por idioma. **`pt_BR` é obrigatório**; os
     demais (`en`, `es`, `ja`, `zh_TW`…) são opcionais. Quem usa um idioma sem
     tradução vê inglês (`en`) e, se não houver, português. Título com até 150
     caracteres numa linha; mensagem com até 2.000 caracteres (quebras de linha
     com `\n`). O texto aparece como texto simples: HTML não é interpretado.
3. Opcional:
   - `"url"`: página do botão **Conhecer novidades**. Só `https://github.com/mainuan/…`
     ou `https://mainuan.github.io/…`. Vazio: o botão usa a release do primeiro
     programa ou some.
   - `"packages"`: repositórios oficiais cujos programas o usuário poderá instalar
     (ex.: `["mainuan-gestao-drivers"]`). Só **sugere**: nada é instalado sem o
     clique em **Instalar novidades**, a autorização do PolicyKit e todas as
     verificações (release estável, SHA-256, simulação). Vazio: anúncio só
     informativo, sem botão de instalar.
   - `"applies_to"`: limita o anúncio a versões do sistema, com os valores do
     `/etc/os-release` e do `dpkg`: `"version_id"` (ex.: `["2027.1"]`),
     `"distro_id"` (ex.: `["mainuan"]`), `"architecture"` (ex.: `["amd64"]`).
     Vazio: todas as versões suportadas.
4. **Commit changes**. Os computadores veem o anúncio na próxima verificação
   (cerca de 1 minuto depois do login) ou ao abrir o aplicativo.

Exemplo completo:

```json
{
  "schema": 1,
  "enabled": true,
  "id": "gestao-drivers-1-1",
  "version": 1,
  "title": {
    "pt_BR": "Olá! O Mainuan tem novidades.",
    "en": "Hello! Mainuan has news."
  },
  "message": {
    "pt_BR": "Conheça o novo Gestão de Drivers.",
    "en": "Meet the new Driver Manager."
  },
  "url": "https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.1",
  "packages": ["mainuan-gestao-drivers"],
  "applies_to": {"version_id": ["2027.1"]}
}
```

## Parar de anunciar

Edite o arquivo, troque para `"enabled": false` e salve. Nenhuma janela abre
mais; quem já viu o anúncio continua com ele no **Histórico de novidades**.

## Quando a janela aparece de novo

O estado de cada computador fica em `~/.local/state/mainuan-recursos/state.json`,
por `id@version` (ex.: `gestao-drivers-1-1@1`), com a data da primeira
apresentação e a situação: lido (a janela foi mostrada ou fechada), adiado
(**Agora não**, por 24 horas) ou ainda não apresentado.

| Mudança no arquivo | Efeito |
|---|---|
| Corrigir texto, link ou tradução, mantendo `version` | não reapresenta; quem abrir o aplicativo vê o texto novo |
| Nova release de um programa listado | não reapresenta; o botão instala a versão nova |
| `version` aumentada (ex.: `1` → `2`) | anúncio novo: aparece uma vez para todos |
| `id` novo | anúncio novo: aparece uma vez para todos |
| `"enabled": false` | some; nada é apresentado |
| Usuário escolheu **Agora não** | volta no primeiro login depois de 24 horas |

## O que impede a janela automática

Basta uma destas condições para a verificação terminar em silêncio:

- arquivo ausente, `"enabled": false`, JSON inválido, campo desconhecido, campo
  obrigatório ausente, texto grande demais (limite de 64 KiB) ou link fora dos
  sites oficiais;
- `applies_to` não inclui este sistema;
- o usuário já viu o anúncio (mesmo `id` e `version`) ou o adiou há menos de 24 h;
- sem internet ou GitHub indisponível (o cache nunca abre a janela);
- sessão Live (só `--demo` mostra a janela nesse caso);
- o usuário desmarcou **Mostrar novidades ao entrar** no menu do aplicativo
  (gravado em `~/.config/mainuan-recursos/preferences.json`).

Um erro de validação aparece apenas para quem abrir o aplicativo manualmente.

## Arquivos legados

Versões 0.2.2 a 0.3.1 leem `packages.txt` e `message.txt`. Para elas também
ficarem em silêncio, `packages.txt` fica **sem repositórios** (só comentários):
sem repositórios, essas versões não criam edição nova e não abrem a janela.
`message.txt` continua com texto porque, vazio, essas versões mostrariam erro
ao serem abertas manualmente. As traduções `message.<idioma>.txt` foram
removidas: só eram lidas junto com uma edição. Não edite esses arquivos.

Limite conhecido: numa versão ≤ 0.3.1, quem clicou em **Agora não** numa edição
antiga ainda pode vê-la uma última vez após o prazo de 24 horas. Para calar
também esses casos, apague todo o texto de `message.txt`: essas versões passam
a falhar a consulta em silêncio, mas mostram erro quando abertas manualmente.
A solução definitiva é instalar a versão 0.4.0 ou posterior.
