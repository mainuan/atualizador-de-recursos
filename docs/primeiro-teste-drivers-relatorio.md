# Kit do primeiro teste real — 23/10/2026

## Entrega

Diretório de transferência: `dist/primeiro-teste-real/transferir/`.
Transfira somente `kit-mainuan-gestor-1.0.tar.gz` e seu `.sha256` para a VM.
O diretório extraído contém também `LEIA-ME.md`, cópia integral do
[roteiro sequencial](primeiro-teste-drivers-vm.md).

Kit `20261023T053046Z`, gerado em 23/10/2026 às 05:30:46 UTC, válido até
**25/10/2026 às 05:30:46 UTC (02:30:46 de Brasília)**. Não serve para produção.

SHA-256 do arquivo de transferência:

```text
167746a2f510b4d5f4dc076d24a8a0182db9b519b64f5644f94e2989c16f5e65
```

Chave pública APT descartável, fingerprint:
`76EC96650CAC21944C91014ED346FCA891A7AA71`.
As chaves privadas de assinatura APT/catálogo foram descartadas. Somente a chave
TLS do servidor local de testes está no arquivo, protegido com permissão 0600.
Não foram geradas chaves oficiais. O arquivo contém 25 entradas, sem backups,
credenciais de produção ou arquivos de desenvolvimento necessários à execução.

## Artefato oficial aprovado

[Release oficial v1.0](https://github.com/mainuan/mainuan-gestao-drivers/releases/tag/v1.0):
repositório ID 1405529794, release ID 421218277, asset ID 667222935.
Pacote `mainuan-gestao-drivers_1.0_all.deb`, 190846 bytes, SHA-256
`d7a1c98743a204f6b5770c7746cb02b3b4d66c09d2d368966118ac39fa47b912`.

O hash calculado coincidiu com o digest da API GitHub e com o arquivo SHA256SUMS
da release. A release não está protegida como imutável pelo GitHub. O kit congela
os bytes e IDs examinados; não redescobre a release nem segue a tag durante o teste.
O commit resolvido da tag foi registrado como referência observada, sem alegar
atestação do processo de compilação do binário.

Foram inspecionados 156 arquivos/links do payload e os quatro scripts de manutenção.
Os scripts possuem o mesmo hash e somente a operação gerada por debhelper para
remover uma regra sudoers legada. O kit exige sua ausência na VM.
Não foram encontrados módulos, firmware, DKMS, serviços ou autostart no payload.
O link do launcher aponta para o código do próprio aplicativo. O gestor não foi
executado nem instalado no computador principal.

## Restrições deliberadas deste primeiro ensaio

- Instalação exclusivamente pelo Atualizador instalado, sem `--demo`, com resolução,
  simulação, confirmação, progresso e verificação por PackageKit/PolicyKit existentes.
- Fonte APT `file:` assinada com chave descartável; catálogo HTTPS em loopback
  com certificado descartável e assinatura Ed25519 independente.
- Política temporária bloqueia outros candidatos APT. Preferências originais são
  guardadas e restauradas; as fontes normais são preservadas. Atualiza-se somente
  o índice experimental sem limpar índices das fontes normais.
- Dependências obrigatórias devem estar satisfeitas pelos pacotes já instalados.
  Dependências/recomendados não são instalados ou atualizados neste ensaio.
  Qualquer efeito adicional do solver APT ou do PackageKit interrompe a preparação.
- Sem transações reais por scripts. O único caminho de instalação é a confirmação
  explícita na interface do Atualizador e a autorização no agente PolicyKit.
- Snapshot/cópia restaurável comprovada é condição do roteiro. Os scripts recebem
  seu nome, mas não verificam o snapshot gerenciado externamente pelo Boxes.
- Preparação e limpeza recusam computador físico e sessão Live/desconhecida e
  utilizam locks padrão APT/dpkg, sem removê-los ou contorná-los.
- Histórico, cache e sequência anti-retrocesso isolados em estado de testes.
  Não altera a configuração de produção distribuída no código ou no Debian.
- Verificação final compara inventário instalado, inclusive pacotes retidos, e
  hashes de arquivos de módulos/firmware/boot/configuração e lista de módulos.
  Nenhum comando de detecção ou alteração de drivers é executado pelo kit.

## Testes executados localmente

| Ensaio | Resultado e limite |
| --- | --- |
| Suíte completa | 166 testes aprovados; preservados os 147 anteriores e adicionadas 19 regressões do kit. |
| Inspeção do `.deb` | Nome/versão/arquitetura/hash, scripts e caminhos aprovados. |
| Catálogo e APT | Assinaturas verificadas; catálogo contém somente o gestor e fixa SHA-256/versão/arquitetura. |
| TLS | Cadeia e hostname conferidos com OpenSSL em modo estrito, sem instalar CA no host. |
| APT isolado | Índice assinado aceito; candidato confiável; simulação e python-apt propõem somente o gestor 1.0. |
| Atualização concorrente de dependência no índice fictício | Versão 999:999 de ubuntu-drivers-common ficou bloqueada; sem atualização adicional no plano. |
| Dependência ausente na cópia do inventário | Instalação recusada; sem tentar incluir a dependência. |
| Backup/restauração | Testes com arquivos temporários e serviços simulados restauram bytes originais; plano inesperado provoca rollback. Não equivale à restauração do snapshot da VM. |
| Infraestrutura fictícia anterior | Catálogos 1/2, seis `.deb` de dados, TLS, APT confiável e conflito real de lock em raiz descartável aprovados. |
| Arquivo final | SHA externo, inventário de entradas e correspondência com scripts/guia entregues conferidos. |

APT isolado executado em bubblewrap sem rede, com raiz do host somente leitura,
índices/arquivos de estado exclusivamente temporários e cópia do inventário local.
Não comprova quais dependências existem na VM do usuário. Essa condição será
verificada novamente na preparação e no plano real do PackageKit.

Evidências locais: `dist/primeiro-teste-real/testes.log`, `validacao-isolada.json`
e `regressao-infraestrutura.json` no mesmo diretório.

## Pendente na VM do usuário

Executar o roteiro, comprovar snapshot/restauração, conferir dependências efetivas,
realizar simulação PackageKit, cancelar a confirmação e a autorização PolicyKit,
autorizar a instalação e observar o progresso, conferir resultado e ausência de
reinstalação. Esses itens **não foram declarados aprovados** nesta entrega.

A limpeza remove a configuração experimental e restaura os backups. Não remove
o gestor instalado. A restauração integral, incluindo a instalação, deve ser feita
pelo snapshot. Exporte evidências antes de restaurá-lo.

## Alterações no código

Adicionados gerador, assistente VM, verificador isolado, testes e documentação.
A geração TLS existente foi extraída para uma função reutilizada pelos dois kits,
mantendo hostname, validade e servidor anteriores. Durante os testes do kit, a
política genérica foi ajustada para `Pin: release *`, validada pelo APT 3.2; não se
depende de um pin de versão genérico ignorado pelo parser.

Não houve alteração na lógica do aplicativo, instalação, histórico ou publicação.
`publication.toml` continua com `enabled = false` e `bootstrap = false`; a configuração
distribuída continua com `keys: {}`. Sem commit, push, merge, tag ou publicação.
