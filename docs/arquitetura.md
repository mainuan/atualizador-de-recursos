# Análise e proposta de arquitetura

## Fontes analisadas em 22/10/2026

- Original: `tiger-update`, `build.sh`, `build-package.sh`, `packages.txt`,
  `message.txt` e entrada desktop. Bash/YAD, senha recebida pelo programa e TAR
  remoto extraído em `/`; sem validação de assinatura nem confirmação do dpkg.
- [PR #1](https://github.com/mainuan/atualizadorderecursos/pull/1), cabeça
  `643320eb5752c727b6eec0e9db4ebf176796c8cb`: Widgets, worker, adiamento e
  detecção Live aproveitados como padrões. Backend prefixado `mainuan-`,
  `apt-get --only-upgrade` por pkexec e publicação de releases não aproveitados:
  não representam um canal editorial e excluem novos programas. Sem merge.
- [Gestão de Drivers](https://github.com/mainuan/mainuan-gestao-drivers), referência
  `1ef06a66366e8a093c9e5a176b0e4f8647b25ad6`: separação backend/qt, transporte
  QtDBus assíncrono, identificadores exatos, ONLY_TRUSTED, SIMULATE, confirmação,
  nova validação e leitura após Finished. Nenhum import desse aplicativo.

## Proposta adotada

`catalog.py` valida catálogo JSON limitado, assinatura Ed25519, HTTPS, domínio e caminho
oficiais, expiração e sequência contra regressão. Configuração e chaves públicas
são provisionadas pela distribuição; nenhuma chave privada entra no pacote.
`state.py` persiste visualização, adiamento e observação dos pacotes por
id/versão, atomicamente, em XDG_STATE_HOME. Não mistura estado editorial com APT.
`packages.py` lê python3-apt em worker, compara versões Debian e planeja somente
os pacotes anunciados. `packagekit.py` encapsula QtDBus, sem Widgets.
`controller.py` coordena resolução, simulação, confirmação, revalidação e
verificação final. `gui.py` usa paleta e componentes nativos, sem cores fixas.

A assinatura cobre os bytes integrais de `novidades.json`; `novidades.json.sig`
contém a assinatura em base64. Número de sequência crescente e validade curta
limitam replay; uma sequência já aceita não pode mudar de conteúdo. Cache é
revalidado e só atende consulta offline, nunca habilita instalação offline.
O manifesto aceita dados declarativos, rejeita campos desconhecidos e não
contém comandos, scripts, URLs de pacotes ou repositórios.

A sessão KDE inicia o processo em segundo plano; um timer adia a primeira
consulta e verifica a cada hora. Rede e APT ficam fora da thread da interface.
Sessão Live sai antes de rede/APT. Lock por usuário impede duas instâncias.
Novidades compatíveis não apresentadas e adiadas há 24h geram a janela; as demais
ficam no histórico. Abrir uma matéria não significa instalar recursos.

Apenas instalação voluntária de pacotes confiáveis dos repositórios existentes.
Sem refresh global, upgrade geral, Flatpak, pkexec próprio ou política permissiva.
PackageKit/PolicyKit e o agente do Plasma fazem autenticação. Simulação bloqueia
remoções, downgrades, reinstalações e efeitos não reconhecidos. O plano e os
respectivos efeitos são reconstruídos antes da execução; mudanças exigem nova
confirmação. ONLY_TRUSTED e a ausência de ALLOW_REINSTALL/ALLOW_DOWNGRADE
restringem a operação; sem garantia de atomicidade entre confirmação e operação
do daemon.

O modo `--demo` constrói exclusivamente adaptadores em memória: não cria conexão
D-Bus, não consulta APT, não baixa catálogo e não salva estados reais.

## Infraestrutura aprovada

A URL de catálogo é
`https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json`.
Downloads e redirecionamentos permanecem nesse diretório. Matérias inicialmente
usam apenas `https://github.com/mainuan/`, validando o limite do segmento, sem
travessia, codificação percentual ou barras duplicadas. Prefixos e chaves são
configuração administrativa, nunca campos do manifesto. A estrutura de produção
fica desativada com `keys: {}` até a equipe fornecer a chave e assinar o catálogo.
`--demo --test-catalog ... --test-config ...` permite validar uma assinatura de
teste em arquivos locais, sempre com backend em memória.

Contrato conferido com os XMLs PackageKit instalados e o upstream
[enums 1.3.4](https://github.com/PackageKit/PackageKit/blob/v1.3.4/lib/packagekit-glib2/pk-enum.h)
e [backend APT](https://github.com/PackageKit/PackageKit/blob/v1.3.4/backends/apt/apt-job.cpp).
O tratamento de sinais, a serialização uint64/QStringList e a conclusão seguem
esse contrato; a aplicação usa apenas Resolve e InstallPackages (este último
com SIMULATE na preparação). Não oferece métodos de remoção ou upgrade global.

## Ajustes após auditoria

A aceitação durável de sequência passou ao repositório, antes do cache e da
consulta APT; o estado compartilhado entre worker e interface é protegido por
lock. Falha na leitura dos pacotes conserva o catálogo editorial com instalação
bloqueada. A validação do estado usa condições explícitas, inclusive com Python
otimizado. O IPC distingue abertura manual de ativação do autostart e aceita
mensagens fragmentadas. Veja [homologacao.md](homologacao.md) para evidências e
limitações restantes de concorrência/autorizações reais.

## Publicação simplificada após a homologação

A edição humana passa a ser `packages.txt` e `message.txt`. O novo
`tools/publication.py` fica fora do runtime e do pacote do aplicativo. Resolve
releases estáveis oficiais, verifica os `.deb` e mantém uma seleção assinada com
IDs GitHub, commit e hashes. Publica catálogo e APT assinado no mesmo commit
somente quando o workflow for autorizado/habilitado. Mensagem isolada e renovação
não mudam os programas aprovados. A configuração inicial é `publication.toml`.

O contrato do catálogo mantém compatibilidade com os exemplos anteriores e aceita
opcionalmente proveniência, `architecture`/`sha256` por pacote, mensagem multilinha
e ausência de `article_url`. A geração nova sempre fornece pins exatos. Antes da
instalação, o planejamento e as simulações exigem esses bytes/versão/arquitetura;
versões já instaladas adequadas continuam sendo consideradas recebidas.
O rollout inicial precisa usar o aplicativo desta etapa: clientes anteriores,
com validação estrita sem esses campos, rejeitariam a extensão de forma segura.

Não foi implementado `InstallFiles`: o APT gerado resolve a lacuna entre Releases
e PackageKit sem enfraquecer `ONLY_TRUSTED`. A configuração inicial da source e
da chave pública APT é responsabilidade da imagem Mainuan, nunca do catálogo.
Veja [publicacao.md](publicacao.md) e a análise detalhada em
[publicacao-simples-relatorio.md](publicacao-simples-relatorio.md).
