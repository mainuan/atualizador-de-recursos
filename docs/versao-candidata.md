# Candidata de homologação 0.2.0 — rodada 1

**Estado: preparada localmente para homologação; não aprovada para distribuição.**
A branch é `homologacao/rc-0.2.0-1`. Não é uma tag ou release. O pacote mantém a
versão Debian 0.2.0; identifique o binário ensaiado pelo SHA-256 do artefato.
Produção continua desativada.

## Git e escopo da revisão

A base local é `dee91a2c9846638fc883bbd27a8c5cc7eacdace7` (“atualizador antigo”),
com `main` e a referência **local** `origin/main` apontando para esse commit.
A nova branch foi criada sobre essa base, transportando as mudanças existentes
no diretório de trabalho. Nenhum commit foi criado; o código continua sem commit
até a autorização do responsável. A `main` não recebeu mudanças de histórico.

Não foi realizado fetch, push, consulta remota, merge, tag ou release nesta etapa.
Logo, este parecer não afirma que a referência local `origin/main` ainda seja a
mais recente no GitHub. Antes de publicar, o responsável precisa autorizar a
consulta/atualização e revisar qualquer divergência remota.

A comparação inclui arquivos novos ainda não rastreados. Só `git diff --stat`
não os mostra: o diff completo de revisão foi produzido com **índice temporário**,
sem modificar o índice real ou criar commit. Evidências e inventário SHA-256 dos
arquivos presentes estão em `dist/rc-0.2.0-1/`.

### Resumo das alterações em relação à base

- Substituição de Bash/YAD, senha própria e TAR na raiz por Python/PyQt6 Widgets,
  backend separado, PackageKit/PolicyKit e confirmação do estado dpkg.
- Catálogo declarativo Ed25519, validação HTTPS/caminhos, sequência/expiração,
  cache autenticado, histórico e adiamento de 24 horas.
- `packages.txt`/`message.txt` restauram a publicação simples; automação congela
  releases/artefatos, extrai metadados Debian e prepara catálogo e APT assinados.
- Integração KDE/Wayland, ícone, menu, autostart adiado, instância única e bloqueio
  de sessão Live/desconhecida, com modo de demonstração sem instalação.
- Empacotamento Debian, testes, workflows com actions fixados por SHA e guia
  de chaves/Environment/GitHub App. Gates de produção fechados.
- Remoção do launcher/desktop/banner antigos e substituição dos construtores.

Nesta rodada não foram adicionadas funcionalidades nem alterado o runtime.
A revisão não encontrou falha nova que exigisse correção de código. Foram
preparadas a branch, evidências, pacote de transferência e instruções adicionais
para executar os ensaios de integração que ainda faltam.

### Pull Request experimental #1

Foi considerado o parecer em `arquitetura.md`, referente ao head experimental
`643320eb5752c727b6eec0e9db4ebf176796c8cb`. O backend experimental com pkexec,
prefixo obrigatório e `apt-get --only-upgrade` não foi incorporado. A candidata
parte da base principal local, sem merge/cherry-pick do PR #1. Seu estado remoto
atual não foi consultado nem alterado.

Depois de um push autorizado, abra uma revisão própria desta branch. Se o PR #1
continuar aberto, a equipe deve decidir manualmente como registrar a substituição;
não misturar as implementações nem mesclar o PR antigo para “atualizar” a candidata.

## Arquivos sensíveis e workflows

A revisão dos arquivos destinados ao Git não encontrou blocos de chave privada,
tokens conhecidos, credenciais em URLs ou arquivos de credenciais reais. Foram
conferidos código, documentação, configurações e padrões conhecidos de segredos;
isso não é prova matemática de ausência de todo segredo arbitrário.

Existem chaves **TLS descartáveis** em kits locais sob `dist/`, ignorado pelo Git.
Elas não entram no commit, no `.deb` ou no pacote de transferência da candidata.
O kit de instalação real deve ser gerado dentro da VM. Não usar `git add -f dist`,
`git add --ignored`, ou transportar diretórios privados da equipe.

Os workflows foram verificados localmente quanto a YAML, Bash/Python embutido,
SHAs fixos, token padrão de leitura, checkout sem credenciais persistidas,
restrição de produção a `main` oficial/Environment/gate, ausência de eventos de
PR no publicador e escrita via App só depois da verificação do conjunto.
O workflow de construção aceita PR e não tem Secrets editoriais.

`actionlint`, `gitleaks` e `trufflehog` não estavam instalados; não foram baixados.
Não houve execução no GitHub nem revalidação remota dos SHAs nesta etapa. A regra
de build por push é apenas `main`: um push nesta branch não dispara esse evento;
a CI pode ser validada por um PR autorizado, ou por execução manual quando o
workflow estiver disponível no repositório. O publicador permanece bloqueado na
branch de homologação, e a configuração local também mantém produção inativa.

## Resultados e limites

As evidências desta rodada ficam em `dist/rc-0.2.0-1/`:

- `testes.log`: suíte completa de 133 testes.
- `workflows.json`: sintaxe, ações fixadas e limites da verificação local.
- `seguranca-arquivos.json` e `arquivos-candidatos.json`: varredura e inventário.
- `diff-completo.stat`, `diff-completo.patch`: comparação completa com a base.
- `kit-validado.json`: APT/TLS/solver/locks em ambiente isolado, sem instalação.
- `debian/`: ciclo dpkg em raiz descartável, menu/ícone/launcher do prefixo,
  demo instalado, remoção/reinstalação e preservação de configuração/estado.
- `blur-claro/`, `blur-escuro/`: demo em Wayland com os esquemas reais BlurGlassy
  aplicados só ao processo, em 640×480, sem trocar tema global.

Os ensaios isolados não comprovam menu global, login real, autenticação, instalação
pelo PackageKit, concorrência com Discover, Live real ou consumo total em VM de
2 GiB. Esses resultados continuam **pendentes**, até preencher a matriz abaixo.

O ambiente encontrado foi uma instalação física Mainuan 2026, Wayland, cerca de
11,5 GiB de RAM e raiz ext4. `/dev/kvm` existe, mas não foram identificados binário
de hypervisor, imagem/VM utilizável ou snapshot com restauração comprovada nos
locais inspecionados. Timeshift presente não constitui essa prova. Nenhuma
instalação de pacotes ou CA/source/keyring foi executada no sistema principal.

## Transferir a candidata e executar a VM

O arquivo local `dist/rc-0.2.0-1/mainuan-rc-0.2.0-1.tar.gz` contém somente fonte,
`.deb`, instruções e checksums. Não inclui `.git`, Secrets, chaves privadas nem
kits antigos. Não é uma release; pode ser copiado para a VM por mídia/pasta
compartilhada escolhida pelo responsável, sem depender de publicar no GitHub.

1. Em seu hypervisor, crie VM com ISO Mainuan oficial já obtida por canal
   confiável: **2048 MiB de RAM**, 2 CPUs e disco de pelo menos 25 GiB. Instale
   normalmente, não use o modo Live para o ensaio principal. Se ainda não tiver
   hypervisor/ISO, obtenha-os/configure-os antes; não executar o ensaio no host.
2. Desligue a VM e crie checkpoint completo **A-limpa** pelo hypervisor, incluindo
   disco/firmware necessários. Ligue, crie `~/canario-antes-da-restauracao`,
   desligue/restaure A, ligue e comprove que o arquivo sumiu. Sem prova, pare.
3. Copie o arquivo de transferência e seu SHA-256 por canal confiável. Na VM:

   ```bash
   tar -xzf mainuan-rc-0.2.0-1.tar.gz
   cd mainuan-rc-0.2.0-1
   sha256sum -c SHA256SUMS
   cd fonte
   ```

   Checksums identificam os bytes transferidos; compare também o hash externo
   do arquivo com aquele entregue pelo responsável. Não são assinatura oficial.
4. Execute, em ordem, o [roteiro completo da VM](homologacao-producao-vm.md),
   começando pelas dependências e geração de `/tmp/mainuan-kit-vm`. Gere as chaves
   descartáveis **na VM**, com validade nova; o `.deb` já estará em `fonte/dist/`.
5. Para logout/login e reinício, use a variante de servidor systemd indicada no
   roteiro. Preencha os testes de menu/autostart, Live e 2 GiB detalhados ali.
6. Exporte apenas evidências sem credenciais e restaure A ao terminar.

## Matriz de aprovação da candidata

Só marcar “aprovada” quando cada item obrigatório tiver evidência do ambiente
real e do mesmo binário identificado por hash. “Não executado” não é aprovação.

| Critério | Evidência objetiva exigida | Estado nesta entrega |
| --- | --- | --- |
| Revisão local | 133 testes, sintaxe, pacote e ausência de segredos destinados ao Git | Executado localmente |
| Snapshot | Arquivo canário desaparece após restaurar checkpoint completo | Pendente |
| Autenticação | Desafio real do agente KDE; cancelamento sem recursos instalados | Pendente |
| Instalação PackageKit | Autorização, progresso e Finished; três pacotes configurados em 1.0 | Pendente |
| Estado real | Instalação externa reconhecida; reabrir sem reinstalação; atualização para 2.0 comprovada pelo dpkg | Pendente |
| Falhas e confiança | Arquivo ausente/adulteração/replay/indisponibilidade sem sucesso falso ou instalação indevida | Pendente na VM; controles automatizados passam |
| Concorrência | APT e Discover reais: esperar/recusar/revalidar, sem remover ou contornar locks | Pendente |
| Integração | Menu/ícone e janela corretos, login novo com autostart após cerca de 60 s, uma instância | Pendente no desktop instalado |
| Live | `--check` encerra sem notificação; abertura manual explica bloqueio e não oferece instalar | Pendente em Live real |
| Blur-Glassy | Claro/escuro e decorações legíveis no compositor real | Demo local passou; VM/decoração pendentes |
| 2 GiB | Sem OOM/travamento; repouso sem crescimento contínuo, consulta utilizável | Pendente |
| Rastreabilidade | Hash do `.deb`, ISO, snapshot, horários, logs e resultados anexados | Hash local preparado; resultados da VM pendentes |

Para a avaliação de 2 GiB, use como limites de aceitação desta rodada: PSS do
aplicativo em repouso ≤150 MiB, pico de RSS na consulta ≤350 MiB, CPU em repouso
≤5% de um núcleo em uma janela de 30 s, e ausência de congelamentos de interface
maiores que 2 s. São critérios de ensaio propostos com margem sobre as medições
locais anteriores; ainda precisam ser medidos na VM, incluindo a pressão do desktop.
Se algum limite falhar, registre o caso e investigue antes de aprovar.

## Comandos de commit e push — executar somente após autorização

Não foram executados. Revise o diff e confira novamente a lista se houver edição
posterior a este parecer. Os comandos de adição incluem as remoções antigas e
as novas pastas, preservando `dist/` fora do Git:

```bash
git switch homologacao/rc-0.2.0-1
git status --short --branch
git add -- .gitignore .github README.md LICENSE build.sh build-package.sh \
  packages.txt message.txt publication.toml bin catalogo data debian docs examples src tests tools
git add -u -- banner.png tiger-update tiger-update.desktop
git diff --cached --check
git diff --cached --stat
git diff --cached --name-status
git commit -m "Preparar candidata de homologação do Atualizador de Recursos"
git push --set-upstream origin homologacao/rc-0.2.0-1
```

Antes do push autorizado, confira com a equipe se a base remota avançou. Atualizar
referências remotas ou resolver divergências não está autorizado por esses
comandos de exemplo nesta entrega. Não usar force-push, merge automático ou
reaproveitar o PR #1 sem revisão. Se as regras exigirem commits assinados, use a
identidade de assinatura Git da equipe; ela é independente das chaves do catálogo/APT.

## Chaves oficiais e recomendação

**Recomendação: candidata interna para homologação, sem aprovação de lançamento.**
Depois da matriz real aprovada e da revisão da branch, os responsáveis podem
seguir o [guia de configuração inicial](configuracao-inicial-producao.md): definir
custódia, gerar os dois pares oficiais distintos, distribuir apenas as chaves
públicas, configurar App/Environment/regras/Secrets e autorizar o primeiro canário.
Essa sequência não foi executada. Mantidos `enabled=false`, `bootstrap=false`,
chaves públicas de produção vazias e aplicativo com `keys: {}`.
