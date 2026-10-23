# Preparar a primeira publicação oficial

Este guia é para o responsável pelo Mainuan. Leia na ordem. **Nenhuma das etapas
administrativas abaixo foi executada nesta entrega.** O catálogo permanece
inativo. Comandos de geração de chaves oficiais, configuração do GitHub e
ativação são instruções para execução futura, depois de autorização da equipe.
Não copie os comandos de instalação para o computador principal de desenvolvimento.

Há três momentos distintos:

| Momento | O que se faz |
| --- | --- |
| Uma vez | Homologar a VM, criar/proteger credenciais, configurar Actions e entregar confiança pública à imagem/canários. |
| A cada lançamento | Publicar releases testadas; editar `packages.txt` e `message.txt`; salvar pelo fluxo autorizado. |
| Antes de liberar aos usuários | Conferir a publicação completa, atualizar índices no canário e comprovar a instalação real. |

## 1. Confirmar o ponto de partida

Use um checkout revisado deste projeto e o Python da distribuição. Execute:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
bash build-package.sh
```

Resultado esperado: testes aprovados e `.deb` em `dist/`. As dependências são
`python3-pyqt6`, `python3-apt`, `python3-cryptography`, `dpkg-dev` e `gnupg`.
Para o probe isolado, também `bubblewrap`; para administrar secrets, GitHub CLI
(`gh`) na máquina administrativa. Instale dependências pelo APT do ambiente
apropriado, não por comandos remotos do catálogo.

Ainda será necessário **autorizar e enviar este código revisado ao GitHub**.
A implementação local, por si só, não instala workflows no servidor. Nesta
entrega não houve commit, push ou merge.

A leitura integral de `publicacao.md` e `publicacao-simples-relatorio.md`, seguida
da conferência do código, confirmou: duas chaves de assinatura, provisionamento
APT inicial e proteção das referências ainda precisam de configuração. Uma
consulta somente de leitura ao GitHub encontrou `main` sem proteção e a lista de
rulesets vazia, na referência `dee91a2c9846638fc883bbd27a8c5cc7eacdace7`.
Isso é uma observação desta revisão, não uma garantia sobre o estado futuro.
Secrets e variáveis remotos **não foram inspecionados**; não é possível afirmar
se já existem. O administrador precisa conferi-los em Settings.

## 2. Homologar primeiro, sem credenciais oficiais

Siga [o roteiro de VM descartável](homologacao-producao-vm.md) até o fim. Ele usa
catálogo e APT assinados com chaves descartáveis, três pacotes de texto, snapshot,
PackageKit e agente PolicyKit reais. Não usa GitHub Secrets, chave oficial ou
catálogo de produção. Registre os resultados e prove a restauração do snapshot.

Resultado esperado: instalação/cancelamento/falha reais conferidos no dpkg,
sem reinstalação desnecessária. O teste `--demo` e a simulação APT não substituem
essa etapa. Se a VM não estiver disponível, registre a pendência e não avance
para ativação.

## 3. Entender as credenciais

| Credencial | Para que serve | Quem recebe a parte pública |
| --- | --- | --- |
| Ed25519 do catálogo | Confirma a origem e os bytes do catálogo e do registro de publicação. | Aplicativo, em configuração administrativa. |
| OpenPGP/GPG do APT | Autentica os índices APT, que contêm os hashes dos `.deb`. | APT, em keyring limitado por `Signed-By`. |
| Chave do GitHub App | Obtém token temporário para publicar arquivos na branch protegida. Não assina catálogo nem pacotes. | O GitHub administra a identidade do App; não distribuir essa chave aos usuários. |

**Use pares distintos para catálogo e APT.** Embora GPG também possa usar
Ed25519 internamente, os formatos/protocolos são diferentes. O APT não entende
a assinatura JSON do catálogo e o aplicativo não usa OpenPGP para autenticá-lo.
Separar os pares também permite substituir uma credencial sem trocar a outra.

As três partes privadas pertencem ao ambiente administrativo e aos Secrets
restritos de produção. Nunca entram em Git, no `.deb`, em artefatos públicos ou
em logs. Não use `set -x`, `cat` da chave privada ou comandos com o conteúdo da
chave em argumentos. O diretório GPG de trabalho contém material privado também.

## 4. Gerar as duas assinaturas, após autorização, em armazenamento seguro

**Esta seção gera chaves oficiais: só o responsável autorizado deve executá-la.**
Use uma máquina controlada e um volume já criptografado/montado. Substitua o
caminho abaixo pelo volume real; não crie uma pasta comum e suponha que ela está
criptografada. Trabalhe fora do repositório.

```bash
umask 077
DIRETORIO_CHAVES='/media/usuario/volume-criptografado/mainuan-recursos'
install -d -m 0700 "$DIRETORIO_CHAVES" "$DIRETORIO_CHAVES/publicos"
export DIRETORIO_CHAVES
```

Resultado esperado: diretório privado no volume seguro. Faça backup também em
outro meio criptografado e com acesso restrito. Permissão 0600 não cifra arquivos.

### 4.1 Catálogo

A partir da raiz do checkout revisado:

```bash
/usr/bin/python3 tools/catalog.py keygen \
  --private-key "$DIRETORIO_CHAVES/catalogo.pem" \
  > "$DIRETORIO_CHAVES/publicos/catalogo.pub"
```

Resultado esperado: PEM privado 0600, sem senha, e chave pública base64 em
`publicos/catalogo.pub`. A ferramenta recusa sobrescrever a chave. O arquivo
público é o que o aplicativo precisa; não entregue o PEM aos usuários.

Registre a impressão da chave pública para conferência por outro canal:

```bash
/usr/bin/python3 - "$DIRETORIO_CHAVES/publicos/catalogo.pub" <<'PY'
import base64, hashlib, pathlib, sys
key = base64.b64decode(pathlib.Path(sys.argv[1]).read_text().strip(), validate=True)
assert len(key) == 32
print('SHA-256 da chave pública do catálogo:', hashlib.sha256(key).hexdigest())
PY
```

Resultado esperado: 64 caracteres hexadecimais. Esse comando lê somente a chave
**pública**. Registre o valor com a equipe por canal administrativo independente.

### 4.2 APT: opção simples com chave dedicada

Este roteiro usa uma chave exclusiva para assinatura APT de CI, com validade de
um ano e sem senha interativa: o workflow precisa assinar sem pedir uma senha.
O armazenamento deve continuar cifrado e o Secret restrito. Não use sua chave
GPG pessoal ou uma chave usada em outros serviços.

```bash
install -d -m 0700 "$DIRETORIO_CHAVES/gpg-apt"
gpg --homedir "$DIRETORIO_CHAVES/gpg-apt" --batch \
  --pinentry-mode loopback --passphrase '' \
  --quick-generate-key 'Mainuan - Assinatura APT de Recursos' ed25519 sign 1y
FPR_APT="$(gpg --homedir "$DIRETORIO_CHAVES/gpg-apt" --batch --with-colons \
  --fingerprint --list-keys | awk -F: '$1 == "fpr" {print $10; exit}')"
export FPR_APT
gpg --homedir "$DIRETORIO_CHAVES/gpg-apt" --batch \
  --output "$DIRETORIO_CHAVES/publicos/mainuan-recursos-archive.gpg" \
  --export "$FPR_APT"
gpg --homedir "$DIRETORIO_CHAVES/gpg-apt" --batch --armor \
  --output "$DIRETORIO_CHAVES/apt-ci.asc" --export-secret-keys "$FPR_APT"
gpg --homedir "$DIRETORIO_CHAVES/gpg-apt" --fingerprint "$FPR_APT"
```

Resultado esperado: keyring público binário `.gpg`, arquivo **privado** `apt-ci.asc`
e fingerprint completo exibido. Confirme que existe só a chave desejada nesse
diretório. Guarde também o certificado de revogação gerado em
`gpg-apt/openpgp-revocs.d/` no backup seguro; não publique um certificado de
revogação por engano. Monitore e renove a chave antes de vencer.

Para uma política com **mestra offline e subchave de assinatura**, peça a um
responsável por GPG para gerar a mestra de certificação e uma subchave de
assinatura, exportar somente `--export-secret-subkeys` para CI e conferir que o
export contém o stub da mestra (`sec#`), sem seu segredo. A subchave exportada
precisa estar operável sem pinentry no workflow; mantenha a mestra e revogação
fora do GitHub. O publicador aceita essa configuração: `apt_fingerprint` continua
sendo o fingerprint completo da chave pública principal. Essa é a opção recomendada
quando houver custódia GPG disponível; não improvise a remoção de senha da mestra.
[Referência GnuPG sobre exportação de subchaves](https://gnupg.org/documentation/manuals/gnupg/Operational-GPG-Commands.html).

## 5. Preparar apenas a configuração pública

Volte à raiz do checkout revisado, na mesma sessão de terminal. O código abaixo
preenche os campos públicos automaticamente; não é edição de catálogo JSON.
Ele exige a configuração inicial ainda vazia e preserva produção desabilitada.

```bash
/usr/bin/python3 - <<'PY'
import base64, json, os, pathlib, re, tomllib
safe = pathlib.Path(os.environ['DIRETORIO_CHAVES'])
public = (safe/'publicos/catalogo.pub').read_text().strip()
assert len(base64.b64decode(public, validate=True)) == 32
fpr = os.environ['FPR_APT']
assert re.fullmatch('[0-9A-F]{40,64}', fpr)
path = pathlib.Path('publication.toml')
raw = path.read_text()
policy = tomllib.loads(raw)
assert policy['enabled'] is False and policy['bootstrap'] is False
assert policy['catalog_public_key'] == '' and policy['apt_fingerprint'] == ''
raw = raw.replace('catalog_public_key = ""', 'catalog_public_key = ' + json.dumps(public))
raw = raw.replace('apt_fingerprint = ""', 'apt_fingerprint = ' + json.dumps(fpr))
path.write_text(raw)
config = json.loads(pathlib.Path('data/atualizador-recursos.json').read_text())
config['keys'] = {policy['catalog_key_id']: public}
out = safe/'publicos/config-cliente.json'
with out.open('x') as stream:
    json.dump(config, stream, ensure_ascii=False, indent=2)
print('Política pública preenchida; produção continua desativada. Configuração de cliente criada.')
PY
```

Resultado esperado: `publication.toml` com a parte pública e fingerprint, ainda
`enabled=false` e `bootstrap=false`; `publicos/config-cliente.json` separado para
os canários. O arquivo padrão `data/atualizador-recursos.json` permanece desativado.
Não coloque a pasta de chaves no checkout. Confira ainda arquitetura e
`distribution_ids`/`distribution_versions` em `publication.toml` usando os valores
reais da imagem:

```bash
cat /etc/os-release
dpkg --print-architecture
```

Faça a leitura na VM Mainuan de destino. Não suponha `ID=mainuan`: há imagens com
`ID=ubuntu`. O canal atual aceita somente uma arquitetura nativa (inicialmente
`amd64`), além dos `.deb` `all`.

Os endereços iniciais já definidos são:

```text
Catálogo: https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json
APT:      https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/apt/
Matérias: https://github.com/mainuan/...
```

São caminhos reservados; o APT não passa a existir antes da primeira publicação.
Não distribuir uma source APT para toda a base enquanto esse endereço retornar
404 ou não tiver assinatura validada.

## 6. Proteger a branch antes de cadastrar secrets

No GitHub, como administrador da organização, configure regras para `main`.
Use dois rulesets independentes, em modo **Active**:

1. **Histórico:** bloquear exclusão e force-push; sem exceção para o publicador.
2. **Revisão:** exigir Pull Request, aprovação de responsável pelo código e o
   check de testes `build`. Invalidar aprovações após alterações e exigir revisão
   do último push. A exceção para este ruleset será somente o App do passo 7,
   para publicar os arquivos gerados. Não liberar bypass para autores de PR.

Defina uma equipe real com acesso de escrita e mantenha um `.github/CODEOWNERS`
revisado, inclusive para o próprio arquivo. Exemplo a adaptar ao nome real:

```text
* @mainuan/SUA-EQUIPE-RESPONSAVEL
```

Confirme na interface que o proprietário é válido. Sem revisão obrigatória no
ruleset, CODEOWNERS sozinho não impede alterações. Inclua administradores na
política de revisão; não coloque contas de uso cotidiano numa exceção ampla.
Quem pode alterar `src/`, `tools/`, política ou workflows pode alterar o código
que verá os Secrets: essas mudanças precisam de revisão de alguém confiável.
[Proteção de branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches).

O GitHub precisa reconhecer o check `build` de uma execução revisada antes de
selecioná-lo como obrigatório. Autorizar o envio inicial do código e essa primeira
execução de testes é parte do provisionamento, sem credenciais editoriais.

## 7. Criar uma identidade de publicação com privilégio limitado

`GITHUB_TOKEN` continua **somente leitura** no workflow preparado nesta revisão.
Não presuma que `contents: write` permitiria ignorar PR obrigatório. Use um GitHub
App exclusivo, instalado somente neste repositório:

1. Organização Mainuan → Settings → Developer settings → GitHub Apps → New.
2. Escolha nome exclusivo, por exemplo “Publicador de Recursos do Mainuan”.
   Homepage: o repositório oficial. Desative webhook; não precisa de callback OAuth.
3. Repository permissions: **Contents: Read and write**. Metadata: leitura
   automática. Não conceder Administration, Actions, Workflows ou acesso a outros
   repositórios. O App não precisa criar releases, tags ou gerenciar secrets.
4. Permita instalação só nessa organização. Instale em **Only select repositories**
   → `atualizadorderecursos`.
5. Anote o **App ID**, não o Client ID. Gere/download uma private key na página
   do App e mova o `.pem` diretamente ao volume seguro, como
   `DIRETORIO_CHAVES/github-app.pem`. Não a imprima.
6. Adicione **somente esse App** à bypass list do ruleset de revisão, modo Always,
   pois o bot fará push direto de catálogo/APT. Não dar bypass ao ruleset que
   bloqueia force-push/exclusão. Confirme regras de organização herdadas também.

O token gerado será temporário, solicitado com `permission-contents: write` só
para esse repositório e revogado pelo action ao terminar o job. O workflow confere
que o commit gerado só toca os quatro arquivos de metadados e `apt/`. Essa
restrição em código complementa a revisão; a permissão Contents do GitHub não é
uma permissão nativa por caminho. A chave do App deve receber a mesma custódia
que os demais Secrets.
[Action oficial para tokens de App](https://github.com/actions/create-github-app-token).

## 8. Criar Environment, variáveis e Secrets

Repository Settings → Environments → crie **publicacao-recursos**:

- Deployment branches and tags: **Selected branches and tags**, regra do tipo
  **Branch**, nome exato `main`. Não liberar tags ou padrões amplos.
- Para a primeira publicação, exija reviewer confiável, prevent self-review e
  desabilite bypass administrativo das regras de deployment, quando disponível.
- Não replique esses secrets no nível do repositório/organização para os jobs de PR.

Os secrets só ficam disponíveis depois das regras de proteção do Environment.
Com prevent self-review, quem iniciou a execução não poderá aprová-la; combine
previamente um segundo responsável confiável para a primeira publicação.
[Configuração oficial de environments](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments).

Cadastre estes **Environment secrets**:

| Nome | Conteúdo privado |
| --- | --- |
| `CATALOG_PRIVATE_KEY` | PEM completo de `catalogo.pem`. |
| `APT_PRIVATE_KEY` | ASCII-armored de `apt-ci.asc` (chave APT exclusiva ou subchave operável de CI). |
| `PUBLICATION_APP_PRIVATE_KEY` | PEM baixado do GitHub App. |

Em Environment variables, cadastre `PUBLICATION_APP_ID` com o App ID numérico.
Em **Repository variables**, cadastre `RECURSOS_PRODUCAO` com valor `false`.
Esse gate precisa estar no nível do repositório, pois é consultado antes de
iniciar o job/Environment. Não se trata de um secret.

Para não exibir chaves privadas na tela, a equipe pode usar `gh`, já autenticado
como administrador autorizado, em vez de copiá-las pelo terminal:

```bash
gh auth login --hostname github.com --web
gh secret set CATALOG_PRIVATE_KEY --env publicacao-recursos \
  --repo mainuan/atualizadorderecursos < "$DIRETORIO_CHAVES/catalogo.pem"
gh secret set APT_PRIVATE_KEY --env publicacao-recursos \
  --repo mainuan/atualizadorderecursos < "$DIRETORIO_CHAVES/apt-ci.asc"
gh secret set PUBLICATION_APP_PRIVATE_KEY --env publicacao-recursos \
  --repo mainuan/atualizadorderecursos < "$DIRETORIO_CHAVES/github-app.pem"
gh variable set PUBLICATION_APP_ID --env publicacao-recursos \
  --repo mainuan/atualizadorderecursos --body 'SUBSTITUIR_PELO_APP_ID_NUMERICO'
gh variable set RECURSOS_PRODUCAO --repo mainuan/atualizadorderecursos --body false
```

Resultado esperado: nomes dos secrets cadastrados, sem valores no log. Esses
comandos **alteram o GitHub**; são instruções futuras, não foram executados aqui.
Não execute `gh secret set` com a chave privada em `--body` ou com `echo`.
Confirme nas configurações que o runner é hospedado pelo GitHub, que o workflow
somente usa código revisado da `main` e que Actions pode executar os actions
fixados por SHA. Em Settings → Actions → General → Workflow permissions,
use o padrão de leitura. Deixe desmarcada a permissão para Actions criar/aprovar
PRs. A escrita usa o token específico do App, não uma ampliação do token padrão.

## 9. Revisar antes de autorizar a primeira publicação

Ainda com `RECURSOS_PRODUCAO=false`, revise:

- VM real aprovada e restaurável, sem confiança de teste levada à produção.
- Releases públicas estáveis, artefatos `.deb` completos e testados, com SHA-256
  na API GitHub; nomes reais em `packages.txt`, mensagem em `message.txt`.
- Política pública, compatibilidade da ISO, proteção de código, App e Environment
  aprovados. Verifique se branch rules/organização não bloqueiam o App.
- Backup protegido das credenciais e procedimento de revogação; confirme as duas
  impressões públicas por canal independente.
- Canário pronto para receber **somente** keyring/configuração públicos. Usuários
  gerais ainda sem o gate de confiança do catálogo ativado.

O workflow de construção não usa Environment, credenciais editoriais ou token de
escrita. O de publicação não tem eventos de PR/`pull_request_target`, restringe
repositório e referência e faz checkout de `${{ github.sha }}` com credenciais não
persistidas. Código e arquivos baixados dos programas não são executados no CI.

## 10. Primeira publicação controlada — somente após autorização específica

**Pare aqui até a equipe autorizar publicar. Estes passos ativam a infraestrutura.**

1. Em alteração revisada, mude `enabled=true` e `bootstrap=true` em
   `publication.toml`. `bootstrap` só se aplica à primeira edição, sem histórico.
   Mantenha o gate remoto `RECURSOS_PRODUCAO=false` durante a revisão.
2. Após essa alteração chegar à `main`, defina `RECURSOS_PRODUCAO=true` na
   Repository variable. Execute Actions → Publicar recursos aprovados → Run
   workflow, branch **main**. Para o bootstrap, não é preciso marcar atualizar
   programas: a primeira edição seleciona a lista toda.
3. O reviewer confere commit, diff, releases e resultado da homologação, então
   autoriza o Environment. A execução gera/valida os dois formatos de assinatura,
   confere catálogo/APT juntos e só depois obtém token do App para publicar.
4. Resultado esperado: um commit automático contendo `catalogo/novidades.json`,
   `.sig`, `publicacao.json`, `.sig` e o APT, sem mudanças em código/entradas.
   Se houver erro, nenhuma publicação parcial é enviada. Se a main avançou,
   o push é rejeitado sem force; execute novamente a partir da main atual.
5. Em revisão posterior, volte **bootstrap=false**, preservando `enabled=true`.
   Nunca reabilitar bootstrap para recuperar registros apagados.

Não distribua chaves privadas para conferir a publicação. Obtenha uma cópia do
commit publicado (com Git, numa pasta nova) e valide com as chaves públicas já
conferidas no passo 4:

```bash
git clone https://github.com/mainuan/atualizadorderecursos.git /tmp/mainuan-publicado
/usr/bin/python3 tools/verify-publication.py /tmp/mainuan-publicado \
  --config "$DIRETORIO_CHAVES/publicos/config-cliente.json" \
  --apt-keyring "$DIRETORIO_CHAVES/publicos/mainuan-recursos-archive.gpg"
```

Resultado esperado: “Publicação verificada”, sequência e número de pacotes.
O verificador confere assinatura Ed25519, registro, ambas as assinaturas APT,
validade, índices normais/por hash/comprimidos e bytes/metadados de todos os `.deb`.
É um verificador estático: não prova que essa seja a edição mais recente do mundo;
a proteção de sequência no cliente exige preservar seu estado local.

Confira também os endereços HTTPS públicos (`curl` lê, não instala):

```bash
curl --fail --proto '=https' --tlsv1.2 \
  https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/apt/InRelease \
  --output /tmp/mainuan-InRelease-publicado
```

Se o GitHub/CDN servir edições desencontradas, aguarde propagação e repita a
validação; não desligue assinaturas. A conferência via APT no canário a seguir
valida a cadeia de hashes efetivamente entregue por HTTPS, além do checkout Git.

## 11. Provisionar confiança pública no canário e depois na imagem

**Execute somente na VM canário restaurável**, com arquivos públicos recebidos
por canal administrativo autenticado. Copie apenas `publicos/`, nunca o diretório
que contém as chaves privadas. Confira o fingerprint público APT antes:

```bash
gpg --show-keys --with-fingerprint ./publicos/mainuan-recursos-archive.gpg
sudo install -Dm644 ./publicos/mainuan-recursos-archive.gpg \
  /usr/share/keyrings/mainuan-recursos-archive.gpg
sudo tee /etc/apt/sources.list.d/mainuan-recursos.sources > /dev/null <<'SOURCES'
Types: deb
URIs: https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/apt/
Suites: ./
Architectures: amd64
Signed-By: /usr/share/keyrings/mainuan-recursos-archive.gpg
SOURCES
sudo apt-get update
sudo install -Dm644 ./publicos/config-cliente.json /etc/mainuan/atualizador-recursos.json
mainuan-atualizador-recursos
```

Resultado esperado: APT aceita `InRelease` sem ignorar confiança/validade; o
aplicativo reconhece o catálogo e apresenta os programas. Abra como usuário
normal. Prepare a operação, confira dependências e autorize no agente PolicyKit.
Valide versões/estado dpkg e reabra: os recursos devem aparecer como recebidos.
O atualizador geral pode atualizar os índices; este aplicativo não faz refresh
APT global. Índice antigo ou candidato diferente do aprovado bloqueia instalação.

Só depois do canário aprovado distribua esses arquivos **públicos** pela imagem,
provisionamento administrativo ou atualização Mainuan já autenticada. Não
bootstrapar confiança baixando uma chave desconhecida pelo mesmo endereço que
ela vai validar. O pacote atual inclui configuração vazia por projeto; sua
instalação sozinha não ativa confiança. Planeje a gestão dos conffiles para não
perder rotações ou sobrescrever personalizações locais inadvertidamente.

## 12. Rotina repetida a cada lançamento

1. Publique releases estáveis testadas nos repositórios Mainuan, com `.deb` prontos.
2. Atualize `packages.txt` (nomes de repositórios, nunca versões/URLs).
3. Atualize `message.txt` (mensagem livre).
4. Salve os dois no GitHub, preferencialmente em um commit pelo editor web.

Com as proteções recomendadas, “salvar” cria um **PR para revisão**; a revisão e
entrada na main são passos administrativos adicionais justificados para impedir
código/entradas não autorizados. Na primeira publicação existe também aprovação
do Environment. Não há JSON, versão de catálogo ou assinatura manual.

Para aprovar novas versões de repositórios já listados, os bytes de `packages.txt`
precisam mudar (por exemplo, alterando um comentário de aprovação). Salvar conteúdo
idêntico não dispara publicação. Alternativamente, use a opção de aprovar novas
releases em Run workflow. Mensagem isolada não muda os programas. Detalhes em
[publicacao.md](publicacao.md).

A renovação semanal não escolhe novas releases. Se o Environment continuar
exigindo reviewer, a renovação também aguardará aprovação: monitore esse estado
para não ultrapassar 30 dias. Depois da fase controlada, a equipe pode revisar
se a proteção por PR/CODEOWNERS/branch já permite dispensar a revisão de deployment;
não relaxar as referências, a revisão de código ou a proteção dos Secrets.
Monitore também expiração GPG, limite de pool (256 MiB) e falhas de Actions.

## 13. Interrupção, recuperação e rotação

- **Falha antes do push:** a main e a última publicação ficam intactas. Corrija a
  causa e rode de novo com main atual. Não copiar arquivos de um runner falho.
- **Job perdeu resposta do push:** consulte o histórico remoto antes de repetir.
  A transação Git publica um commit inteiro; não há meio catálogo no commit.
  Publicação pode ter concluído mesmo se o runner terminou depois com erro.
- **Propagação CDN:** assinaturas/hash impedem aceitar um par incorreto. Pode
  haver indisponibilidade transitória; não contorne a confiança.
- **Indisponibilidade prolongada/expiração:** o app recusa expirados; cache válido
  serve apenas consulta, sem instalação. Renove a mesma seleção com nova sequência.
- **Programa funcionalmente ruim:** suspenda novas aprovações; publique correção
  Debian com versão maior. O atualizador não faz downgrade/rollback do sistema.
- **Arquivos gerados danificados:** suspenda o gate remoto; preserve cópias e
  identifique o commit íntegro de **maior sequência já publicada**. Restaure o
  conjunto completo desse mesmo commit (catálogo, registro, índices e pool),
  e renove por publicação normal, preservando pisos e sequência. O publicador
  autentica o estado anterior mesmo se vencido; o verificador final exige a nova
  edição ainda válida. Não
  restaurar uma edição menor se algum cliente já recebeu uma maior. Se o único
  backup é anterior, há perda do estado de segurança: recuperação supervisionada
  deve reconstruir a maior sequência/pisos antes de voltar a publicar.
- **Backup:** mantenha cópia do commit completo de cada edição publicada, do
  registro assinado, dos hashes/IDs e do inventário de sequências, fora do serviço
  de publicação. Um `git bundle` do repositório público não contém as chaves
  privadas se a regra de nunca comitá-las foi respeitada; confira antes de arquivar.

Rotação planejada: distribua primeiro as novas chaves públicas aos clientes e
canários. Para Ed25519, mantenha antiga+nova no cliente; declare a antiga em
`[previous_catalog_keys]` da política, troque o id/chave corrente e Secret, e
publique **sequência maior**. Para APT, entregue keyring com as duas chaves antes
de trocar fingerprint/Secret. Após a cobertura, retire a antiga por canal
administrativo. Rotação da chave do App é independente: atualize seu Secret,
teste e revogue a chave anterior no GitHub.

Em suspeita de vazamento, pare publicação, revogue a credencial atingida e
redistribua confiança por canal administrativo. Não use o catálogo comprometido
para anunciar sua própria chave substituta. A chave comprometida pode ter assinado
estado falso: recuperar esse registro requer avaliação humana.

A sequência é local por usuário: primeira consulta e estado apagado/restaurado
não conhecem edições nunca recebidas. A expiração limita replay, não elimina essa
limitação. Nunca apague estado do aplicativo para “corrigir” uma recusa de catálogo.

## O que falta para o primeiro lançamento oficial

1. Autorizar a publicação do código/workflows revisados no repositório remoto.
2. Disponibilizar VM com snapshot comprovado e aprovar o roteiro real, inclusive
   PolicyKit, PackageKit, versões/pins, falhas/cancelamentos e concorrência.
3. Responsável gerar e custodiar os dois pares de assinatura; conferir e
   distribuir as partes públicas por canal confiável.
4. Administrador configurar rulesets, equipe/CODEOWNERS, GitHub App, Environment,
   três Secrets e duas variáveis; testar permissão de escrita na branch protegida.
5. Aprovar uma rodada de programas reais e compatibilidade da ISO.
6. Autorizar explicitamente bootstrap/primeira publicação; verificar commit,
   HTTPS/APT/catálogo no canário; desabilitar bootstrap e só então ampliar a confiança.

Não existe chave oficial gerada, configuração remota alterada ou produção ativada
por este guia. O roteiro prepara as decisões e comandos; a primeira publicação
continua dependendo dos responsáveis.
