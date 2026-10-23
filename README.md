# Atualizador de Recursos do Mainuan

Canal oficial de novidades em Python 3/PyQt6 Widgets para Mainuan baseado no
Kubuntu 26.04, KDE Plasma 6 e Wayland. Não substitui o atualizador geral APT/Flatpak.

## Usar a versão 0.2.2

```bash
mainuan-atualizador-recursos
```

O modo normal consulta `packages.txt` e `message.txt` da main deste repositório
no **mesmo commit** e descobre as releases estáveis mais recentes com Debian
compatível dos programas oficiais. Não exige VM, argumento especial, chave de
catálogo, GitHub App, repositório APT próprio ou configuração pelo usuário.

O autostart KDE executa `mainuan-atualizador-recursos --check`: consulta após
60 segundos e, depois, a cada hora. Não consulta nem instala na sessão Live ou
quando não consegue confirmar uma sessão instalada. Nada é instalado automaticamente.

Preserva a interface clássica com o beija-flor e os botões **Instalar novidades**,
**Conhecer novidades**, **Agora não**. Histórico, informações técnicas e verificação
manual ficam no menu. Agora não adia a notificação por 24 horas. Visualização e
instalação são estados separados. Versões adequadas já instaladas são reconhecidas,
inclusive por outra ferramenta, sem reinstalação.

## Publicar novidades usando dois arquivos

1. Publique uma release **estável** do programa em seu repositório público da
   organização `mainuan`. Anexe o `.deb` compatível com nome convencional, por
   exemplo `mainuan-gestao-drivers_1.0_all.deb`. O GitHub precisa informar o digest
   SHA-256 do asset na API de releases; sem digest verificável, a instalação é bloqueada.
2. Edite [packages.txt](packages.txt) pela interface web: um repositório por linha.
3. Edite [message.txt](message.txt): mensagem livre, preservando parágrafos.
4. Salve. Não execute assinatura nem edite JSON, versões ou outro arquivo.

Exemplo válido atual de `packages.txt`:

```text
mainuan-gestao-drivers
```

Exemplo de `message.txt`:

```text
Olá! O Mainuan tem novidades.

Confira quais são:
```

É possível listar vários repositórios oficiais. Os nomes amigáveis vêm das
releases e a lista é montada automaticamente. Conhecer novidades abre a página
oficial do primeiro lançamento. Uma nova release estável é descoberta na próxima
consulta, sem recompilar o Atualizador ou alterar os dois arquivos. Não substitua
artefatos/tags já distribuídos: publique uma versão nova.

Leia [Publicação e segurança do canal GitHub](docs/canal-github.md) e as
[notas de lançamento 0.2.2](docs/v0.2.2.md).

## Segurança da instalação

A consulta inicial baixa somente metadados. Após clicar em instalar, verifica
InstallFiles, baixa os pacotes por HTTPS e confere tamanho, SHA-256 e os campos
internos Package/Version/Architecture. Verifica dependências, simula e revalida a
operação antes da autorização nativa do PolicyKit. Alterações fora dos pacotes
anunciados são bloqueadas. As dependências devem estar satisfeitas no sistema.

HTTPS e o digest publicado pelo GitHub **não equivalem à assinatura de um
repositório APT**. Advertências nativas sobre origem não confiável são preservadas.
O aplicativo não captura senhas nem altera políticas administrativas. O sucesso
só é informado após conferir as versões realmente instaladas.

Sem conexão, preserva histórico/cache para consulta e bloqueia a instalação.
Registra IDs, commits e digests localmente; rejeita substituições de artefatos e
retrocessos de versões já observadas. Esses controles não protegem contra
comprometimento da própria conta oficial do GitHub ou do usuário local.

## Testar e empacotar

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
bash build-package.sh
lintian dist/mainuan-atualizador-recursos_0.2.2_all.deb
```

Demo não consulta rede/APT/D-Bus nem altera pacotes. O pacote é `Architecture: all`,
sem ELF/bibliotecas nativas incorporados. Usa Python/Qt/PyQt6 da distribuição,
sem compilação nativa nem requisitos próprios x86-64-v2/v3/v4. O teste do conjunto
da distribuição em processador v1 real permanece pendente.

O GitHub Actions testa, constrói o Debian, verifica arquitetura e executa Lintian.
A tag autorizada `v0.2.2` publica o pacote e `SHA256SUMS` como release estável.

## Histórico

O publicador antigo Ed25519/APT/GitHub App está **desativado**, inclusive para
execução manual, e não é acionado por alterações nos dois arquivos. Documentos e
ferramentas antigos são históricos, sem uso no fluxo normal. `publication.toml`
continua desabilitado. A configuração antiga em `/etc/mainuan/` não é exigida nem
alterada pelo novo canal. `--homologacao-github` permanece apenas como ensaio
histórico isolado; não é necessário para utilizar 0.2.2.

Licença GPLv3 preservada do TigerOS. Mainuan Gestão de Drivers é referência de
arquitetura, sem dependência direta entre os aplicativos.
