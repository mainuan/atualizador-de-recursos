# Entrega: simplicidade de publicação recuperada

Este relatório registra a etapa dos 129 testes. A preparação posterior da
infraestrutura, com GitHub App restrito e verificação conjunta catálogo/APT,
está no [roteiro inicial](configuracao-inicial-producao.md) e no
[relatório da revisão de infraestrutura](preparacao-infraestrutura-relatorio.md).

A administração cotidiana voltou a usar **dois arquivos**, editáveis no GitHub.
O catálogo continua declarativo e assinado; os programas passam das releases
para um APT assinado gerado automaticamente, antes de serem oferecidos ao
PackageKit. Produção permanece desativada e nenhuma operação Git de publicação
foi executada nesta etapa.

## Análise do TigerOS

Foram examinados diretamente os quatro arquivos do
[projeto original](https://github.com/Tiger-OperatingSystem/feature-update-manager):

| Arquivo | Funcionamento original |
| --- | --- |
| [packages.txt](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/main/packages.txt) | Um nome por linha; continha `feature-update-manager`. |
| [build.sh](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/main/build.sh) | Aceitava URL direta ou buscava `Tiger-OperatingSystem/REPO/releases/download/continuous/REPO.deb`. Extraía com `dpkg -x` em uma árvore temporária, reunia os arquivos num TAR e gerava `CURRENT`. |
| Controle de versão | `date +%y.%m.%d%H%M%S` gravado em `var/tiger-update/version`, também copiado para `CURRENT`; o cliente comparava igualdade com sua marca local. Não eram versões Debian. |
| [message.txt](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/main/message.txt) | Texto livre; a mensagem consultada descrevia atualizações separadas para as séries 23 e 25. |
| [tiger-update](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/main/tiger-update) | Escolhia Plasma/Xfce, buscava mensagem e `CURRENT` nas variantes do repositório, mostrava YAD e baixava o TAR da release `continuous`. Capturava senha no programa e extraía na raiz com sudo. |

O procedimento administrativo era pequeno, mas a instalação não passava pelo
registro de pacotes nem pelo resolvedor de dependências; a checagem TAR não
provava autenticidade. Foi preservada a edição dos dois arquivos. Não foram
retomados TAR na raiz, senha própria, tags `continuous` como identidade de
conteúdo ou sucesso sem confirmação do dpkg.

## Implementação

- `packages.txt` volta à raiz com **mainuan-gestao-drivers**, repositório real.
  `message.txt` contém a saudação em português. O [guia](publicacao.md) traz os
  exemplos completos e as instruções pela interface web.
- `tools/publication.py` resolve releases estáveis oficiais, verifica SHA-256 dos
  artefatos e lê Package/Version/Architecture do control. Congela bytes e IDs;
  mantém registro assinado, pisos históricos e histórico editorial.
- `tools/publish-catalog.py` lê as entradas e a política inicial, recebe as chaves
  por ambiente protegido e só aceita o contexto do workflow da `main` oficial.
- `.github/workflows/publish-resources.yml` prepara, valida e assina o catálogo e
  o APT, depois publica o conjunto num único commit automático **quando for
  futuramente habilitado**. Falhas de validação/assinatura e conflito na branch
  impedem a publicação. O workflow não foi executado remotamente nesta entrega.
- `publication.toml` concentra a configuração inicial. Política desabilitada,
  chaves vazias, bootstrap desabilitado e variável GitHub de habilitação exigida.
  As credenciais não são oferecidas ao workflow de PR/construção.
- Runtime preserva separação PyQt6/backend e acrescenta pins opcionais de versão,
  arquitetura e hash; compara os pins também na simulação. Mensagens multilinha
  são texto simples; matéria pode faltar, com fallback oficial validado.
- Saudação solicitada e nomes amigáveis permanecem em Widgets nativos. A revisão
  visual identificou repetição da saudação quando ela já estava na mensagem;
  a interface agora a exibe uma vez, preservando espaço em telas pequenas.
- Build/CI passam a incluir GnuPG como dependência de **construção/testes**;
  o aplicativo não carrega o publicador nem recebe chaves privadas.

Não foi incluído `InstallFiles`. O contrato existe no PackageKit 1.3.4 instalado,
mas um `.deb` obtido via GitHub e autenticado pelo catálogo não adquire confiança
APT automaticamente. Usar o repositório assinado conserva `ONLY_TRUSTED`, o
resolvedor de dependências e o agente PolicyKit do Plasma. O [guia](publicacao.md)
documenta source e keyring iniciais. O aplicativo não os instala por manifesto.

### Releases posteriores e mensagens

Alteração somente de mensagem congela a seleção anterior, sem consultar releases
novas. Alterar a lista (inclusive comentário) ou aprovar explicitamente uma nova
seleção no Actions permite buscar versões novas de todos os programas listados.
A renovação semanal preserva os anúncios e apenas renova validade/assinatura.
A atualização posterior de uma tag/release não troca os bytes já distribuídos.
Republicar bytes diferentes na mesma versão ou voltar para versão menor falha.

O título da release fornece o nome amigável; o control fornece nomes reais dos
pacotes. Quem já tem versões adequadas aparece como **Já recebido**, sem
reinstalação. Uma mensagem nova pode criar uma edição editorial, mas não força
reinstalação dos mesmos pacotes. Abrir a matéria continua sendo só visualização.

## Verificação com repositório real

Consulta pública e download **somente para leitura**, sem instalação:

- Repositório oficial: `mainuan/mainuan-gestao-drivers`, ID `1405529794`.
- Release `v1.0`, ID `421218277`; commit resolvido
  `d84fdd9c75acca7c69e3e07912f4f0f064b4d1e7`.
- Artefato ID `667222935`; control: pacote `mainuan-gestao-drivers`, versão `1.0`,
  arquitetura `all`.
- SHA-256 conferido com o GitHub:
  `d7a1c98743a204f6b5770c7746cb02b3b4d66c09d2d368966118ac39fa47b912`.
- O repositório é um **fork oficial**. A validação foi ajustada para aceitar forks
  pertencentes à organização autorizada, preservando verificações de proprietário,
  publicação e bytes. Rejeitar todo fork impediria o exemplo real solicitado.
- `mainuan/mainuan-welcome` retornou 404 nas consultas públicas e foi excluído do
  exemplo ativo. O publicador não aceita completar um catálogo ignorando essa falha.

Essas observações representam a consulta desta etapa; não certificam que a
release foi homologada funcionalmente nem garantem disponibilidade futura.
Evidência local: `dist/publicacao-auditoria/repositorio-real.json`.

## Testes e demonstração

**129 testes aprovados**, incluindo todos os **101 testes anteriores** e
28 testes novos de publicação e integração com o aplicativo.

| Cenário pedido | Resultado |
| --- | --- |
| Um ou vários repositórios aprovados | Aprovado; três DEBs reais de dados fictícios, títulos amigáveis e metadados internos. |
| Repositório inexistente | Bloqueado, sem saída parcial. |
| Debian ausente | Bloqueado com identificação do repositório. |
| Nome Debian diferente do repositório | Aprovado; usa o control interno. |
| Release draft/prerelease ainda não aprovada | Bloqueada. |
| Mensagem alterada sem programas novos | Seleção exata preservada, sem consulta GitHub; sem reinstalação. |
| Atualização de release já distribuída | Exige aprovação nova; pins e histórico preservados. |
| Versão antiga ou mesma versão com bytes diferentes | Bloqueada, inclusive após remover/reincluir repositório. |
| Chave oficial ausente / produção desabilitada | Bloqueio explícito. Testes continuam com chaves descartáveis. |
| Falha de assinatura editorial/APT | Bloqueio; inclui falha real GnuPG e verificação de assinatura inválida. |
| Todos os recursos já recebidos | Plano completo, sem pacotes pendentes; visualizar não muda para instalado. |
| Registro/pool adulterado, redirect indevido, artefato posterior | Bloqueados. |
| Candidato APT posterior ao aprovado | Bloqueado, sem contornar candidato/pinning APT; divergência de hash bloqueada na simulação. |
| Rotação planejada de chave | Assinatura nova com continuidade da sequência anterior. |
| Catálogo gerado → GUI, sem matéria específica | Nomes exibidos, fallback oficial e estado apenas visualizado. |

`tools/demo-publication.py` produziu duas edições assinadas para três repositórios
fictícios; versões 1.0 e 2.0. Os seis DEBs contêm apenas dados, sem scripts de
instalação. Chaves privadas descartadas ao final. Saída em
`dist/publicacao-ficticia-final/`; não inclui chave oficial.

`tools/probe-publication.py` confirmou as duas edições com **APT real em
bubblewrap**, host somente leitura e sem rede: `apt-get update` e simulação do
resolvedor retornaram código 0, candidatos confiáveis, pins conferidos e status
dpkg temporário vazio ao final. Nenhum pacote foi instalado no host.

Interface fictícia executada em **Wayland/Breeze**, paletas clara e escura
aplicadas só aos processos, resolução **640×480**: três programas em lista com
rolagem, botões dentro da janela, confirmação, progresso e conclusão simulados.
Capturas próprias da aplicação em `dist/publicacao-auditoria/interface-*/`.
Memória observada: cerca de 48–54 MiB PSS e 160–168 MiB RSS, incluindo diálogos.
A medição é do demo; não substitui ensaio de instalação/consumo em VM de 2 GB.

Também foram validados sintaxe YAML/Bash dos workflows, compilação Python,
construção local do Debian e estrutura do pacote. GitHub Actions remoto e seus
Environment/Secrets/regras da branch permanecem pendentes de configuração e
execução autorizada. Os workflows não foram apresentados como homologados na
infraestrutura remota.

## Configuração inicial e pendências

O [procedimento completo](publicacao.md) cobre custódia/backup das duas chaves,
Secrets do environment restrito, chave pública editorial no cliente, keyring APT
com `Signed-By`, source oficial, bootstrap inicial, rotação, monitoramento de
validade e limitações do armazenamento Git. Nada disso passa a ser tarefa diária.

Ainda dependem de autorização e ambiente apropriado: provisionar chaves oficiais,
regras e Secrets no GitHub; primeiro commit/publicação automática; configuração
APT da imagem; homologação PackageKit/PolicyKit real com esses pacotes em VM com
snapshot, incluindo dependências, concorrência e autenticidade. Permanecem também
as pendências de VM/2 GB registradas em `vm-final.md`.

A implementação e a demonstração local estão prontas para revisão. **Não há
recomendação de ativar produção antes dessas etapas.** Nenhuma chave oficial foi
gerada; nenhum commit, push, merge, tag ou release foi realizado.
