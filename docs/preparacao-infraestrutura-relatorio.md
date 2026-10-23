# Auditoria e preparação da infraestrutura

O [guia inicial](configuracao-inicial-producao.md) contém a ordem completa de
execução e os comandos para o responsável. O [roteiro da VM](homologacao-producao-vm.md)
separa testes reais dos ensaios locais não destrutivos. **Produção desativada.**

## Documentos e componentes revistos

Leitura integral de `publicacao.md` e `publicacao-simples-relatorio.md`, seguida
pela conferência de workflows, `publication.toml`, publicador/assinador,
catálogo/cache/estado, planejamento APT, empacotamento e kit de VM. Os relatórios
anteriores conservam seus números históricos; esta revisão acrescenta os pontos
abaixo, sem alegar que a configuração remota foi executada.

## Pendências e correções identificadas

| Ponto | Constatação e tratamento |
| --- | --- |
| Proteção remota | Consulta GET à branch `main` retornou `protected=false`; rulesets retornou lista vazia. Referência observada `dee91a2c9846638fc883bbd27a8c5cc7eacdace7`. Nenhuma regra foi alterada. |
| Escrita em branch protegida | `contents: write` sozinho não garante bypass de revisão. Workflow preparado para GitHub App exclusivo, com instalação em um repositório e token temporário. Token padrão agora somente leitura. Configuração do App/bypass permanece tarefa administrativa. |
| Confiança das referências | Mantidos eventos sem PR, restrição a repositório/main, checkout por SHA e Environment. Guia exige CODEOWNERS válido/revisão e separa ruleset de histórico daquele com exceção de revisão para o App. |
| Credenciais | Dois secrets editoriais mais secret da chave do App; Environment variable do App ID e Repository variable do gate. Valores remotos não foram lidos nem cadastrados. |
| Cadeia catálogo/APT | Novo `tools/verify-publication.py` confere ambas as confianças públicas, assinaturas e correspondência dos artefatos. Entrada de produção exige esse teste antes de obter token de escrita. |
| Caminhos de publicação | Workflow recusa staged files fora dos quatro metadados e `apt/`, antes de criar o commit. Isso não equivale a permissão nativa por caminho; o código com acesso à chave do App continua precisando de revisão. |
| APT antes do bootstrap | Documentação ajustada: source só chega aos canários depois de o endereço HTTPS existir e estar válido. Evita configurar um repositório ainda em 404 na base inteira. |
| Validação de VM | Kit atualizado com pins de versão, arquitetura e SHA-256. Probe isolado compara esses pins com candidatos APT reais. Roteiro novo cobre também APT HTTPS local e reconhecimento de instalação externa. |
| Renovação com reviewer | Tornado explícito: reviewer no Environment também impede renovação semanal até aprovação; exige monitoramento. Não prometer renovação sem intervenção sob essa política. |
| Actions de construção | Checkout/upload fixados por SHA; checkout não persiste credenciais. Construção/PR não recebem credenciais de produção. |

## Resultado da auditoria de segurança

**Catálogo e registro.** Ed25519 autentica bytes antes de processar os lançamentos.
Formato, limites, prefixos HTTPS/caminhos, validade e sequência são verificados.
A sequência/digest do cliente é persistida antes de planejar pacotes. Erro de
assinatura não vira fallback para um cache antigo; cache offline válido é só consulta.

**Pacotes.** Download público de releases confere tamanho/digest GitHub e lê
control sem executar scripts. O pool usa nomes por SHA-256. Registro preserva
IDs de repositório/release/asset, commit, versões/arquiteturas e pisos históricos.
Mesmo nome/versão/arquitetura com bytes diferentes é recusado; versão menor que a
maior distribuída também. Mensagem isolada/renovação não escolhe releases novas.
Uma nova seleção dos programas é uma aprovação explícita de todos os nomes da lista.

**Substituição de release.** Tags mutáveis não identificam o pacote congelado.
Uma substituição futura não troca o pool já aprovado; download em corrida com
mudança de asset falha por digest/tamanho/data. Recomenda-se release immutability
no GitHub também. O processo confia na aprovação inicial pelo Mainuan e na conta
GitHub: não verifica atestação de build nem prova que o `.deb` foi compilado do
commit registrado. Assinar não substitui revisão e testes do programa.

**Consistência.** GPG autentica Release/InRelease; hashes autenticam índices e
arquivos. O verificador novo também exige texto de InRelease igual a Release,
Packages/Gzip equivalentes, índices por hash correspondentes, todos os `.deb` com
control correspondente e conjunto do pool igual ao registro assinado. Pacotes
oferecidos no catálogo precisam existir nesse APT com os mesmos pins.

**Instalação e recursos existentes.** APT somente leitura compara versões Debian;
PackageKit resolve/simula e PolicyKit autoriza. Origens, holds, dependências,
remoções/reinstalações/downgrades e pins são conferidos novamente antes de instalar.
Recursos configurados por APT/Discover/outro meio, na versão mínima suficiente ou
superior, são reconhecidos como recebidos sem reinstalação. Isso observa o dpkg,
não certifica os bytes de todos os arquivos já instalados. Visualização/adiamento
continuam separados; conclusão real exige estado dpkg e Finished bem-sucedido.

**Interrupções.** Arquivos são gerados em staging, verificados antes da escrita e
publicados em um commit Git sem force. Conflito impede publicação; se o job perder
a resposta após push, consultar remoto antes de repetir. CDN pode servir pares
de edições diferentes temporariamente: cliente/APT recusam inconsistências.

**Recuperação/rotação.** Guia exige backup completo da maior sequência publicada,
sem restaurar sequência/pisos menores. Renovação autentica estado anterior mesmo
expirado, então emite sequência maior. Troca de chave começa distribuindo confiança
pública nova, conserva o contador e só depois remove a antiga. Incidente com chave
comprometida exige revogação e recuperação supervisionada, sem confiar no registro
potencialmente forjado por essa chave.

**Limites.** Anti-replay local por usuário não fornece conhecimento de edições
nunca recebidas. Apagar/restaurar estado perde o ponto de referência. Verificador
estático com duas chaves públicas não prova sozinho a última edição disponível.
Validade e preservação dos registros são necessárias. O instalador não faz
rollback do sistema; correção funcional deve usar versão Debian maior.

## Verificações executadas nesta revisão

- **133 testes aprovados**: preservados os 129 existentes, mais quatro testes
  do verificador conjunto. Cobrem conjunto válido, adulteração de índices/pacotes/
  assinatura APT, APT válido de outra edição e ausência de chave APT confiável.
- Verificador público executado contra edição fictícia 2: **6 `.deb` históricos**,
  duas edições editoriais, assinaturas e catálogo/APT consistentes. Nenhuma chave
  privada é necessária para esse comando.
- Novo kit descartável gerado: duas edições assinadas, três pacotes 1.0/2.0, SHA-256
  e arquitetura `all`. Probe verificou TLS estrito, arquivos sem scripts/executáveis,
  índices APT confiáveis, plano com pins e solver, e conflito de lock real na
  configuração APT isolada. Zero instalações no host.
- YAML e sintaxe Bash dos dois workflows conferidos; Bash e Python embutido dos
  guias validados sintaticamente. Não equivale a executar configurações remotas.
- Configurações locais continuam `enabled=false`, `bootstrap=false`, chaves
  públicas de produção ausentes, `keys: {}` no aplicativo e sem `.sig` oficial.

Evidências locais em `dist/preparacao-producao/`: `testes.log`,
`publicacao-verificada.log`, `kit-validado.json` e kit descartável. A validade de
kit/CA é de dois dias; gerar novamente para um ensaio posterior. Não foram
instalados CA, source, keyring ou pacote no sistema principal.

## Trabalho administrativo ainda necessário

O fim do [guia inicial](configuracao-inicial-producao.md) traz a lista de liberação.
Em particular: autorizar envio do código revisado; VM/snapshot e matriz real;
custódia dos dois pares de assinatura; App/Environment/regras/Secrets/variáveis;
programas reais aprovados; bootstrap autorizado; validação HTTPS e instalação
no canário antes de entregar confiança à base geral.

Nenhum teste de instalação real/PolicyKit foi declarado aprovado nesta revisão.
Não foram criadas chaves oficiais, alterado o GitHub ou executados commit, push,
merge, tag, release ou ativação automática.
