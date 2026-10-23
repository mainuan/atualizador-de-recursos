# Publicação atual: canal GitHub 0.2.2

**Use [Publicação pelo canal GitHub](canal-github.md).** Basta publicar releases
estáveis oficiais, editar `packages.txt` e `message.txt`. O modo normal não depende
de catálogo assinado, chaves, GitHub App ou repositório APT próprio.

O restante deste documento registra a infraestrutura anterior, atualmente
**desativada**, e não deve ser seguido para publicar novidades na versão 0.2.2.

## Registro histórico: publicação com catálogo/APT

A rotina do administrador passa a usar apenas `packages.txt` e `message.txt`.
**Não há JSON, versão de catálogo ou assinatura para preencher a cada publicação.**
A produção continua desativada nesta entrega.

Para preparar a infraestrutura, siga o
[roteiro de configuração inicial, em ordem e com comandos](configuracao-inicial-producao.md).
Ele inclui a identidade GitHub App necessária para publicar na branch protegida
e o [ensaio de instalação real em VM](homologacao-producao-vm.md).

## Rotina cotidiana

1. Desenvolva, teste e publique uma release **estável**, pública, no repositório
   oficial `mainuan/NOME`. Anexe os `.deb` completos antes de publicar a release.
   Draft e prerelease não são aprovações para distribuição. A publicação estável
   pelo mantenedor e a edição da lista na `main` autorizada constituem a aprovação.
2. No GitHub, edite `packages.txt`, com um repositório por linha:

   ```text
   mainuan-gestao-drivers
   ```

   Esse repositório e seu `.deb` foram verificados. `mainuan-welcome` não foi
   encontrado publicamente e não foi colocado na lista. Para vários programas,
   acrescente outros **nomes reais**, cada um em sua linha. Não coloque URLs,
   nomes de pacotes Debian ou versões. Linhas vazias e comentários `#` são aceitos.
3. Edite `message.txt` livremente em português:

   ```text
   Olá! O Mainuan tem novidades.
   Confira quais são:
   ```

   Quebras de linha são preservadas, até 2.000 caracteres. Texto vazio usa a
   mensagem padrão. A interface sempre lista os nomes amigáveis dos programas,
   mesmo quando a mensagem não os descreve; HTML permanece texto simples.
4. Salve os dois arquivos, preferencialmente em **um único commit pelo editor
   web do GitHub** (`github.dev`, tecla `.`). Nenhum comando local é necessário.
   Edições em commits separados também funcionam, mas podem produzir duas
   edições editoriais se ambas as execuções chegarem a publicar.
5. Acompanhe a execução **Publicar recursos aprovados** em Actions. Uma falha
   não publica a parte válida da lista: corrija o problema e publique novamente.

O nome amigável vem do título da release, com descrição do repositório/nome como
fallback. Os nomes técnicos e as versões vêm do **control interno do Debian**,
independentemente do nome do repositório ou do arquivo. Não existe inferência
`nome-do-repo == nome-do-pacote`. Cada repositório pode fornecer vários pacotes;
nomes duplicados entre repositórios ou dois artefatos elegíveis para o mesmo
pacote são recusados. O canal inicial destina-se a `amd64`, aceitando também
pacotes `all`; outros canais precisam de configuração própria.

### Atualizar um programa que já está na lista

Uma nova release no repositório do programa **não entra sozinha** no catálogo.
Alterar só `message.txt` preserva exatamente os programas já aprovados. Isso evita
que uma correção de texto incorpore código novo sem querer.

Para aprovar novas versões dos programas listados, altere `packages.txt` — pode
ser apenas um comentário, por exemplo `# Aprovar novas releases testadas` — e
salve. Ou use Actions → Publicar recursos aprovados → Run workflow → marque
**Aprovar seleção de novas releases estáveis**. Nenhuma versão é digitada.
A seleção é renovada para **todos os repositórios listados** nessa aprovação.
Os programas da lista devem representar a mesma rodada testada pela equipe.

A automação seleciona a release estável publicada mais recentemente até a data
da autorização. Releases/artefatos alterados depois dessa data exigem nova
aprovação; um retry de push não passa a incluir artefatos posteriores. Use versões
Debian crescentes: trocar os bytes de um `.deb` sem mudar a versão é recusado.
Uma versão inferior à maior já distribuída para esse pacote também é recusada,
mesmo se o programa tiver sido retirado da lista e adicionado novamente.

### Matéria opcional

Não é preciso criar uma matéria separada: o botão **Conhecer novidades** abre
por padrão a página oficial da primeira release selecionada. As notas dessa
release podem apresentar o conjunto dos programas. Sua ausência como artigo
independente não bloqueia a publicação. O catálogo admite omitir `article_url`;
nesse caso o aplicativo abre a página oficial de releases do primeiro repositório
ou a página de releases do Atualizador, se não houver proveniência.

Para uma matéria comum específica, a equipe pode configurar `article_url` em
`publication.toml`, inicialmente só sob `https://github.com/mainuan/`. É uma
opção avançada, dispensável na rotina dos dois arquivos. A futura migração para
site próprio exige provisionamento confiável de prefixos no aplicativo e ajuste
da política do publicador; o catálogo não pode autorizar outro domínio.

## O que a automação faz

`tools/publication.py` implementa o fluxo; `tools/publish-catalog.py` é sua entrada
exclusiva de produção. `.github/workflows/publish-resources.yml`:

- Executa em pushes da `main` que alteram os dois arquivos, execução manual
  autorizada ou renovação semanal. Não há gatilho de releases dos outros
  repositórios, `pull_request` ou `pull_request_target`.
- Confere organização, repositório público e ativo, releases estáveis publicadas,
  datas, artefatos disponíveis e SHA-256 informado pelo GitHub. Forks oficiais são
  aceitos: Gestão de Drivers é um fork pertencente ao Mainuan.
- Baixa sem credenciais nos redirects do CDN, confere tamanho/hash e lê o control
  com `dpkg-deb --field`, com limites de tamanho, memória e tempo. Não clona nem
  executa builds, scripts do repositório ou maintainer scripts dos `.deb`.
- Registra ID do repositório, ID da release, SHA do commit Git resolvido, ID de
  cada artefato, versão Debian, arquitetura e SHA-256. Copia os bytes aprovados
  para `apt/pool/SHA256.deb`. Tags e URLs mutáveis não identificam o conteúdo
  distribuído; os IDs/hashes e a cópia congelada o identificam. Ativar **release
  immutability** no GitHub é recomendado como proteção adicional, não substitui
  os hashes nem requer renomear releases existentes.
- Verifica o registro anterior **assinado**, preserva o piso das versões,
  incrementa a sequência, cria histórico editorial (até 50 edições), valida o
  esquema do aplicativo, assina Ed25519 e verifica novamente a assinatura.
- Gera automaticamente um repositório APT plano, `Packages`, `Release`,
  `InRelease`, `Release.gpg`, índices por hash e suas assinaturas OpenPGP.
  Mantém os pacotes e índices anteriores para histórico e corridas com caches.
- Publica `catalogo/` e `apt/` juntos num único commit automático. Sem `force`:
  se a `main` mudou durante o trabalho, o push inteiro falha. A execução seguinte
  precisa partir do estado atualizado; nunca aplicar uma saída antiga à força.
- A renovação semanal muda validade/assinatura/sequência, preservando as edições
  editoriais e os pacotes: não cria novidade nem seleciona versões novas.

`catalogo/publicacao.json` e sua assinatura são o registro da seleção e dos pisos
históricos; não devem ser editados ou apagados manualmente. `novidades.json` é o
catálogo consumido pelo aplicativo. O registro guarda o commit/data da aprovação;
o próprio commit gerado preserva sua relação no histórico Git. Ambos são
assinados com a mesma chave editorial. O estado prévio pode estar expirado para
renovação, mas sua assinatura e ligação com o catálogo precisam continuar válidas.

## Instalação: por que existe um APT adicional

Um `.deb` em GitHub Releases não aparece automaticamente no PackageKit.
O contrato `InstallFiles` existe, prevê instalação de dependências e exige uma
política para arquivos locais não confiáveis; a assinatura Ed25519 do catálogo
não transforma um `.deb` avulso em pacote confiável para o backend APT.

Por isso esta implementação mantém `Resolve`/`InstallPackages`, simulação,
PolicyKit e `ONLY_TRUSTED`, usando o **APT assinado gerado pela publicação**.
Não habilita `InstallFiles`, instalação não confiável, `dpkg -i`, senha própria
ou extração de TAR na raiz. Não instala repositórios/chaves indicados pelo catálogo.
Referência: [XML oficial do PackageKit](https://github.com/PackageKit/PackageKit/blob/v1.3.4/src/org.freedesktop.PackageKit.Transaction.xml)
e [autenticação de pacotes Debian](https://www.debian.org/doc/manuals/debian-handbook/sect.package-authentication.en.html).

Na consulta, o APT do cliente precisa ter índices atualizados pelo mecanismo
habitual da distribuição. Este aplicativo não duplica a atualização geral nem
força refresh global. Índices ausentes/antigos deixam a instalação indisponível
com indicação na lista; a equipe deve confirmar a propagação em canário.

Pacotes gerados pelo publicador ficam fixados em **versão + arquitetura + hash**.
Para quem ainda precisa deles, uma versão posterior no APT não pode substituir
silenciosamente a aprovada. Se o candidato escolhido pelo APT diferir do pin,
a instalação é bloqueada até nova aprovação/configuração administrativa;
o aplicativo não escolhe outra versão para contornar o pinning APT. A preparação/simulação e a revalidação conferem
também o hash esperado. Todas as dependências precisam ter origem APT confiável,
ser resolvidas pelo PackageKit e constar da confirmação. Dependências podem vir
do Ubuntu/Mainuan configurados; dependências impossíveis ou efeitos proibidos
bloqueiam a operação antes da instalação. A automação verifica os artefatos,
mas não certifica compatibilidade funcional nem dependências de toda a ISO;
a release deve ter sido testada pela equipe.

Quem já tem o pacote **configurado na versão aprovada ou superior** recebe
**Já recebido**, sem reinstalação/upgrade adicional por causa do anúncio.
Visualizar ou adiar não prova instalação; a confirmação final continua dependendo
do PackageKit e da versão realmente configurada no dpkg.

## Configuração inicial, uma vez, após autorização

Os passos abaixo são um procedimento futuro. **Não foram executados para produção.**

1. Complete a homologação em VM com snapshot descrita em `vm-final.md`:
   instalação/autenticação reais, cancelamento, dependências, concorrência e Live.
2. Gere a chave oficial Ed25519 em máquina controlada e volume criptografado:

   ```bash
   /usr/bin/python3 tools/catalog.py keygen --private-key /local-seguro/catalogo.pem
   ```

   A ferramenta imprime apenas a chave pública base64 e grava PEM privado 0600,
   sem senha. Guarde backup criptografado e acesso restrito. Não comite a chave.
   O comando de geração não é executado automaticamente.
3. Provisione uma chave OpenPGP **separada** para o APT. Mantenha a chave mestra
   offline, preferindo subchave de assinatura com validade limitada na automação.
   Anote o fingerprint completo e exporte a chave pública. A equipe pode usar
   GnuPG em ambiente controlado; a automação apenas importa a chave já fornecida,
   sem gerar chaves oficiais. O material de assinatura de CI precisa funcionar
   sem pinentry; proteja-o em Secrets, nunca em Git ou artefatos.
4. Configure `publication.toml`: chave pública/id editorial, fingerprint APT,
   arquitetura e `ID`/`VERSION_ID` reais da imagem. A configuração inicial admite
   `ubuntu`/`mainuan`, versões `2026`/`26.04`; confirme a matriz da ISO.
   Habilite `bootstrap` **somente para a primeira publicação**. Depois desabilite;
   apagar o registro não deve reiniciar sequências nem pisos de versões.
5. Crie o Environment **publicacao-recursos**, limitado à branch `main` oficial.
   Coloque `CATALOG_PRIVATE_KEY` (PEM Ed25519 completo) e `APT_PRIVATE_KEY` (export
   privado OpenPGP ASCII-armored da chave/subchave autorizada) como Secrets desse
   environment. Não crie cópias como secrets disponíveis aos workflows de PR.
   Proteja código, política, workflows e branch contra alterações não revisadas.
   Quem pode mudar código executado com secrets pertence à cadeia de confiança.
   Dependências Actions estão fixadas por SHA; construções/PR usam outro workflow
   sem environment nem credenciais editoriais. Cadastre também o Secret
   `PUBLICATION_APP_PRIVATE_KEY` e a Environment variable `PUBLICATION_APP_ID`
   do App restrito descrito no roteiro inicial. Se houver reviewers no environment,
   cada execução exigirá essa aprovação adicional por escolha da equipe.
6. Configure o GitHub App para obter token temporário de escrita somente neste
   repositório, com exceção no ruleset de revisão para os arquivos gerados.
   `GITHUB_TOKEN` é somente leitura. Não conceda bypass a autores de PR ou ao
   bloqueio de force-push/exclusão. Nenhum PAT amplo é necessário. O workflow
   verifica os caminhos staged antes de publicar; código/política precisam de revisão.
7. Prepare a distribuição da chave pública APT por canal administrativo confiável em
   `/usr/share/keyrings/mainuan-recursos-archive.gpg`. Crie uma source `.sources`:

   ```text
   Types: deb
   URIs: https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/apt/
   Suites: ./
   Architectures: amd64
   Signed-By: /usr/share/keyrings/mainuan-recursos-archive.gpg
   ```

   Essa instalação inicial pertence à imagem/pacote de configuração Mainuan,
   nunca a comandos remotos do catálogo. Não usar `trusted=yes`, `apt-key` global
   ou ignorar `Valid-Until`. Confirme o fingerprint fora do canal de download.
   Entregue a source aos canários somente depois de existir APT HTTPS válido;
   evite distribuir uma source que ainda retorna 404 para os demais usuários.
8. Prepare a chave pública editorial no mapa `keys` da configuração administrativa
   `/etc/mainuan/atualizador-recursos.json`. Preserve os prefixos restritos existentes.
   Nenhuma chave privada integra o aplicativo ou o `.deb`. Prepare canários primeiro.
9. Só após decisão explícita da equipe: `enabled = true` na política e variável
   `RECURSOS_PRODUCAO=true` no GitHub. Faça a primeira publicação autorizada,
   desative `bootstrap`, confira par catálogo/assinatura, índices e canário.
   A hospedagem inicial usa o GitHub já existente, sem servidor pago adicional.

Nesta entrega: `enabled=false`, `bootstrap=false`, chaves de publicação vazias,
configuração do aplicativo com `keys: {}`, catálogo inicial sem assinatura, e
nenhuma source APT instalada no host. Os três gates continuam fechados.

### Armazenamento e manutenção

A hospedagem inicial guarda `.deb` pequenos no Git, sem Git LFS: no máximo 25 MiB
por artefato e 256 MiB no pool inteiro. É adequada aos utilitários pequenos do
Mainuan; o histórico Git cresce. Ao atingir o limite, a publicação falha claramente.
Planeje migrar o APT para hospedagem estática oficial adequada antes de grandes
programas; não apague pools/registro para contornar limites. Renovação semanal
mantém validade de 30 dias; monitore falhas do workflow e expiração das chaves.

Caches do GitHub podem temporariamente servir catálogo e assinatura de edições
diferentes: o cliente rejeita o par e não instala. Os índices por hash e pacotes
congelados evitam substituir bytes durante uma operação APT. O prefixo oficial
do catálogo continua o mesmo aprovado inicialmente; a aplicação não baixa `.deb`
por seu leitor de catálogos.

### Rotação e retrocesso

Distribua novas chaves públicas **antes** de usá-las. Para Ed25519, mantenha ambas
no cliente e coloque a anterior em `[previous_catalog_keys]` de `publication.toml`
(`id_antigo = "BASE64_PUBLICO"`), configure a nova chave/id corrente e substitua o
Secret. O publicador autentica o registro anterior pela chave antiga e assina a
próxima sequência pela nova. Depois da cobertura, remova a confiança antiga.
Para APT, distribua um keyring com ambas as chaves antes de trocar Secret e
fingerprint. Não redefina a sequência. Observe preservação de conffiles locais.

Em comprometimento, revogue confiança por canal administrativo, suspenda o
workflow e restaure o último registro confiável por procedimento supervisionado,
com sequência superior à já aceita. Não confie automaticamente num registro
assinado pela chave comprometida. O catálogo nunca altera chaves confiáveis.

O cliente verifica assinatura **antes** de interpretar os lançamentos e persiste
sequência/digest antes de consultar APT. Rejeita sequência inferior ou mesma
sequência com bytes diferentes. O publicador preserva seus próprios pisos
assinados. Ambos dependem de conservar seus estados: um usuário novo ainda não
conhece edições nunca recebidas; uma edição antiga assinada e ainda válida pode
ser aceita nessa primeira consulta. Expiração limita a janela. Não apagar o
estado ou fazer force-push/reverter o registro para recuperar uma publicação.

## Testar todo o fluxo sem modificar o sistema

```bash
/usr/bin/python3 tools/demo-publication.py --output /tmp/mainuan-publicacao-ficticia
/usr/bin/python3 tools/probe-publication.py /tmp/mainuan-publicacao-ficticia \
  --output /tmp/mainuan-publicacao-ficticia/apt-real.json
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo \
  --test-catalog /tmp/mainuan-publicacao-ficticia/edicao-1/catalogo/novidades.json \
  --test-config /tmp/mainuan-publicacao-ficticia/config-teste.json
```

Use diretório novo. A demonstração gera três repositórios/pacotes de dados
**fictícios**, duas edições (1.0 → 2.0), assinaturas reais com chaves descartáveis
e os dois arquivos de entrada. Descarta chaves privadas; não contata GitHub.
O probe exige `bubblewrap`, lê os índices com APT real isolado, sem rede e com
o host somente leitura; roda apenas simulação de instalação. Não adiciona source,
chave, pacote ou estado dpkg no host. A interface usa somente backend simulado.
Troque `edicao-1` por `edicao-2` para ver a novidade posterior. Acrescente
`--scenario instalado`, `erro`, `cancelado` ou `adiado` para ensaiar os estados.
Os botões de matéria abrem páginas fictícias oficiais de teste (não existem).

A suíte não precisa de rede ou chaves oficiais:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

Ferramentas de publicação/testes exigem `python3-cryptography`, `python3-apt`,
`dpkg-dev` e `gnupg`; a interface exige `python3-pyqt6`. As ferramentas
`catalog.py sign/verify` continuam disponíveis para diagnóstico offline e
recuperação supervisionada, não fazem parte da rotina editorial.
