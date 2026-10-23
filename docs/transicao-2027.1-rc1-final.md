# Mainuan 2027.1 RC1 → final: proposta para a construção da ISO

**Estado: arquitetura proposta, sem implementação ou publicação.**
Atualização de compatibilidade 0.2.3: o Atualizador também aceita o contrato
`ID=mainuan`/`VERSION_ID=2027.1` para RC1 e final sobre Kubuntu 26.04. A separação
de campos sugerida neste documento continua uma proposta para o pacote de
identidade, não um requisito do Atualizador nem uma migração já implementada.
Consulte [a política atual](v0.2.3.md); o rootfs real ainda precisa ser conferido.

Esta análise usa o checkout `7b5ede2` do Atualizador 0.2.2 e a instalação de
desenvolvimento disponível em 23/10/2026. Essa instalação é Mainuan 2026 sobre
Ubuntu/Kubuntu resolute; não é uma VM da futura ISO 2027.1 RC1.

Objetivo: atualizar os componentes e promover a identidade para Mainuan 2027.1
final sem reinstalar, mantendo a interface aprovada e a instalação voluntária
por PackageKit/PolicyKit. Não é uma migração para outra versão do Ubuntu.

## 1. Inventário efetivamente realizado

| Caminho observado | Proprietário/condição no ambiente disponível | Destino proposto na RC1 |
| --- | --- | --- |
| `/etc/os-release` | `base-files`; link `../usr/lib/os-release`; não é conffile | Override Mainuan, com diversion registrada somente deste link |
| `/usr/lib/os-release` | `base-files`; arquivo regular, não conffile | Manter os dados originais da base Ubuntu 26.04 |
| `/etc/lsb-release` | `base-files`; **conffile** | Preservar a identificação de compatibilidade Ubuntu 26.04 |
| `/etc/issue`, `/etc/issue.net` | `base-files`; conffiles; mostram Ubuntu 26.04.1 | Não alterar para promover a identidade |
| `/etc/debian_version` | `base-files`; conffile; contém `forky/sid` | Não interpretar como versão do Mainuan nem modificar |
| `/etc/dpkg/origins/ubuntu` | `base-files`; conffile | Preservar o fornecedor da base |
| `/etc/dpkg/origins/default` | Link para `ubuntu`, sem proprietário direto retornado por dpkg-query; criado pelo postinst de base-files | Preservar |
| `/var/log/installer/media-info` | Arquivo gerado, sem proprietário direto retornado | Preservar como proveniência da mídia original RC1 |
| `/etc/hostname`, `/etc/machine-id`, `/var/lib/dbus/machine-id` | Identidade da máquina, não da edição; sem proprietário direto retornado | Nunca alterar na promoção |

Versões observadas: `base-files=14ubuntu6.2`,
`kubuntu-settings-desktop=1:26.04.13`, `lsb-release=12.1-2build1`.
`mainuan-release` não está instalado. Não há diversion de os-release/lsb-release
na lista local. Os scripts instalados de base-files foram lidos; essa observação
não dispensa conferir novamente o pacote exato usado na ISO.

O ambiente atual possui `ID=ubuntu`, `VERSION_ID=2026`, `NAME=Mainuan`,
`PRETTY_NAME="Mainuan 2026 LTS"`. O lsb-release também identifica Mainuan 2026.
`dpkg --verify base-files` acusa diferenças em `/usr/lib/os-release` e
`/etc/lsb-release`. Isso confirma alterações em arquivos de base-files, mas não
identifica qual ferramenta as fez. **Não reproduzir esse método na ISO RC1.**

Antes de fechar a ISO, repetir o inventário dentro de seu rootfs e na instalação
feita por ela. Registrar resultados, hashes e versões na evidência da construção:

```bash
dpkg-query -S /etc/os-release /usr/lib/os-release /etc/lsb-release \
  /etc/issue /etc/issue.net /etc/debian_version /etc/dpkg/origins/ubuntu
dpkg-query -W -f='${Package} ${Version}\n${Conffiles}\n' base-files
readlink /etc/os-release
readlink /etc/dpkg/origins/default
dpkg-divert --list
dpkg --verify base-files
```

São comandos de inspeção. Nenhuma alteração desses arquivos foi executada nesta
etapa. Outros caminhos de identificação adicionados pelo construtor/instalador
da ISO deverão entrar no mesmo inventário; não há checkout do construtor da
ISO RC1 identificado nesta análise para certificar sua lista completa.

## 2. Decisão sobre versão Mainuan e compatibilidade Ubuntu

Recomendação: separar a versão da **edição Mainuan** da versão da **base Ubuntu**.
Não reutilizar VERSION_ID para o ano Mainuan nesta transição. A identificação
humana muda, mas os consumidores Ubuntu continuam recebendo a base correta:

| Campo no override `/etc/os-release` | ISO RC1 | Após promoção final |
| --- | --- | --- |
| `NAME` | `Mainuan` | `Mainuan` |
| `PRETTY_NAME` | `Mainuan 2027.1 RC1` | `Mainuan 2027.1` |
| `VERSION` | `2027.1 RC1 (base Kubuntu 26.04)` | `2027.1 (base Kubuntu 26.04)` |
| `ID` | `ubuntu` | `ubuntu` |
| `ID_LIKE` | `debian` | `debian` |
| `VERSION_ID` | `26.04` | `26.04` |
| `VERSION_CODENAME`, `UBUNTU_CODENAME` | `resolute` | `resolute` |
| `VARIANT`, `VARIANT_ID` | `Mainuan`, `mainuan` | `Mainuan`, `mainuan` |
| `MAINUAN_RELEASE_VERSION` | `2027.1~rc1` | `2027.1` |
| `MAINUAN_RELEASE_STAGE` | `rc1` | `final` |

Os dois campos MAINUAN_* são extensões próprias propostas, não campos padronizados.
A versão Debian ordena a promoção corretamente:
`dpkg --compare-versions '2027.1~rc1' lt '2027.1'` retornou sucesso.

Essa opção preserva a identidade Mainuan na apresentação e evita ensinar
ferramentas Ubuntu que 2027.1 seria uma versão do Ubuntu. No código local de
`aptsources.distro.get_distro()`, ID seleciona a classe Ubuntu e VERSION_ID é lido
como versão da distribuição. `UpdateManager.Core.utils` também lê VERSION_ID.
Não basta acrescentar ID_LIKE para garantir que todo consumidor trate uma nova
combinação `ID=mainuan`/`VERSION_ID=2027.1` corretamente.

Portanto, mudar ID para mainuan ou VERSION_ID para 2027.1 fica fora desta proposta.
Não modificar suites/fontes APT, codename, origin, políticas de atualização ou
executar do-release-upgrade. A transição continua dentro de Kubuntu 26.04.

O override usa a precedência nativa de `/etc/os-release`, sem fundir seus campos
com `/usr/lib/os-release`. A base permanece no arquivo de fornecedor. Referência:
[especificação os-release](https://www.freedesktop.org/software/systemd/man/latest/os-release.html).

## 3. Pacote responsável: mainuan-release

Planejar um repositório oficial `mainuan/mainuan-release`, ainda não criado nesta
etapa, com pacote `mainuan-release`, `Architecture: all`, versões imutáveis:

- `2027.1~rc1`: instalado e configurado pela construção da ISO RC1.
- `2027.1`: publicado somente quando os requisitos da edição final forem definidos
  e a migração estiver homologada.

O Atualizador apenas baixa, valida, simula e solicita a transação. **Não escreve
arquivos de identidade.** A ativação pertence aos scripts locais do pacote,
executados pelo gerenciador de pacotes após autorização. Não receber comandos,
caminhos de escrita ou lista de requisitos executáveis de packages.txt/message.txt.

### Propriedade sem substituir base-files

Não criar um pacote concorrente que instale os mesmos arquivos sem coordenação.
Não usar Conflicts/Replaces amplos contra base-files, --force-overwrite ou cópia
direta sobre seus arquivos. Não fazer fork de base-files para esta solução.

A proposta usa a infraestrutura Debian de diversion **apenas para o link não
conffile `/etc/os-release`**, registrada pelo pacote mainuan-release. O link
original de base-files passa para `/etc/os-release.ubuntu`; futuras cópias desse
link provenientes de base-files seguem o registro. `/usr/lib/os-release` continua
intacto e serve como identificação de fallback da base.

O pacote passa a fornecer `/etc/os-release` como link relativo
`mainuan-release/active/os-release`. O arquivo original não é descartado; a
propriedade e a exceção ficam explícitas no banco do dpkg. A diversion será
estabelecida na instalação inicial do pacote RC1, não refeita na promoção final.

**Não desviar `/etc/lsb-release`, `/etc/issue` ou qualquer conffile.** Antes de
registrar a diversion, o futuro preinst precisa verificar proprietários,
conffiles, destino, link e diversions preexistentes. Se a ISO mudar esse contrato,
ou existir override de administrador/terceiro, abortar e preservar os arquivos;
não assumir que o inventário desta máquina vale para toda imagem.

A escolha ainda exige ensaio de instalação, abort-install, remoção e atualização
de base-files. Durante a instalação inicial, se o override não estiver disponível,
os leitores conformes devem poder usar `/usr/lib/os-release`; não se pode deixar
a identidade indisponível. Não usar essa exceção para desviar arquivos vitais ou
para contornar mecanismos nativos de configuração. Referências:
[diversions na Debian Policy](https://www.debian.org/doc/debian-policy/ap-pkg-diversions.html),
[dpkg-divert](https://manpages.debian.org/unstable/dpkg/dpkg-divert.1.en.html).

### Ativação somente depois da configuração

Os templates novos ficam no payload em namespace próprio de mainuan-release.
**O payload final não contém o arquivo ativo nem substitui o destino ativo da RC1.**
Unpack pode ocorrer antes de dependências estarem configuradas e não promove nada.

Manter gerações completas em `/etc/mainuan-release/generations/`, geradas pelo
pacote, com acesso de escrita exclusivo de root. `active` seleciona uma geração
por link relativo. Cada geração contém todo o os-release, incluindo versão e
estágio Mainuan. Esses dados e links permanecem no filesystem raiz e disponíveis
desde o boot; não depender de /home, rede ou /var separado.

Somente `postinst configure`, após todas as verificações abaixo, prepara uma
geração, grava/sincroniza os dados e troca `active` atomicamente no mesmo filesystem.
Não sobrescrever a geração ativa durante unpack, upgrade ou reinstalação.
`prerm`/`postrm upgrade` não apagam identidade nem removem a diversion.

Reexecuções devem ser idempotentes. Erros anteriores à ativação preservam a RC1
e retornam falha ao dpkg/PackageKit. Interrupção após a troca, mas antes de o dpkg
registrar configured, pode deixar identidade final e pacote pendente de configuração:
isso só é admissível porque os componentes já foram conferidos; a reexecução
deve concluir sem repetir efeitos. Não prometer rollback integral de pacotes.
Referência: [scripts e recuperação no Debian](https://www.debian.org/doc/debian-policy/ch-maintainerscripts.html).

Em remoção/purge, restaurar o link de base-files e remover somente a diversion
pertencente ao pacote, sem destruir arquivos de terceiros. Na remoção abortada,
manter a identidade válida. A reinstalação final valida novamente os requisitos,
sem promover antecipadamente uma instalação quebrada.

## 4. Critério real para chamar o sistema de final

A equipe da ISO precisa fechar a lista de componentes obrigatórios e suas versões
mínimas/exatas. Essa lista ainda não foi fornecida e não é inventada aqui. Nem
Gestão de Drivers nem qualquer driver de hardware são requisitos presumidos.

O pacote final declara os requisitos em **Depends versionados**, gerados da mesma
definição controlada usada para validar a ISO final. Não usar Recommends como
garantia. Evitar ciclos e não introduzir Pre-Depends sem necessidade comprovada.
Referência: [dependências Debian](https://www.debian.org/doc/debian-policy/ch-relationships.html).

Antes de ativar a geração final, o postinst precisa confirmar:

1. Base Ubuntu 26.04/resolute e arquitetura suportada, sem troca de distribuição.
2. Origem RC1/Mainuan correspondente ou reinstalação final válida, sem converter
   um Kubuntu genérico apenas por possuir ID=ubuntu.
3. Cada componente obrigatório presente, em versão permitida pelo comparador
   Debian e estado **install ok installed**. Unpacked, half-configured,
   reinst-required ou configuração/triggers obrigatórios pendentes não bastam.
4. Ausência de conflito/diversion desconhecida e condições para gravar a geração.

O pacote RC1 deve estabelecer desde a ISO o contrato para a futura promoção. Os
scripts não dependem de argumento especial do Atualizador, variável de ambiente
ou teste de VM para liberar a identidade final. A mesma proteção vale para
instalação manual do `.deb`. Não executar apt/dpkg de instalação dentro do postinst,
baixar dependências ali ou confiar somente no sucesso do download/simulação.

Após a instalação, além do estado configurado do pacote, o futuro backend deve
reler a identidade ativa e confirmar `MAINUAN_RELEASE_STAGE=final` e a versão
esperada. Não usar apenas o cache de `platform.freedesktop_os_release()` para
comprovar a mudança feita durante o mesmo processo.

## 5. Ajustes internos previstos antes da ISO RC1

Nenhum destes ajustes foi implementado nesta etapa:

- `session.system_identity()`: separar base (ubuntu/26.04) de variante/versão/estágio
  Mainuan, usando leitura de dados sem execução de shell e leitura fresca para
  confirmar promoção. Não inferir Mainuan apenas de ID=ubuntu.
- `github_channel.py`: manter a compatibilidade pela base; reconhecer a identidade
  Mainuan ativa e, para mainuan-release, confirmar identidade junto do estado
  configurado. Os filtros atuais aceitam VERSION_ID 26.04/2026: o contrato proposto
  mantém 26.04, mas a confirmação da promoção ainda precisa ser adicionada.
- Notificação automática: se mainuan-release já estiver configurado em versão
  adequada **e** a identidade final estiver ativa, não reapresentar essa promoção,
  mesmo com histórico de usuário novo/limpo ou mensagem editorial alterada.
  Consulta manual e histórico podem mostrá-la como recebida, com instalação
  desabilitada. Se outros recursos da edição ainda estiverem pendentes, podem ser
  anunciados sem reinstalar o pacote de identidade. O filtro futuro não deve
  confundir “visualizada” ou “adiada” com “instalada”.
- Consumidores Mainuan: adotar o mesmo contrato de base versus edição, sem criar
  dependência entre aplicativos. No checkout local do Gestão de Drivers, o adapter
  de assinatura DKMS usa ID/ID_LIKE; o verificador `.github/scripts/check_cpu.py`
  exige Ubuntu/26.04. Ambos precisam entrar na matriz de regressão. A busca nos
  checkouts locais welcome/alerta/dot-files não prova cobertura de todos os programas
  que entrarão na ISO; inventariá-los também no rootfs final.

A aparência, os botões, o menu e os fluxos de autenticação não mudam. Não substituir
a detecção positiva de sessão Live por uma heurística baseada no nome Mainuan.

## 6. Publicação como novidade comum: duas fases

O canal atual já descobre múltiplas releases e compara versões Debian, mas
`GitHubChannel.plan(check_dependencies=True)` bloqueia dependências novas e o
validador bloqueia efeitos não anunciados. Não alegar que listar mainuan-release
instala automaticamente todos os componentes da edição final.

**Fase A — componentes:** distribuir/atualizar os requisitos pelo atualizador
normal ou por novidades explicitamente anunciadas e validadas. Se houver novas
dependências não suportadas pelo ensaio de arquivos locais, resolver pelo fluxo
normal de pacotes. Cada componente obrigatório precisa estar configurado antes
da promoção. Não relaxar as proteções do PackageKit para fazer caber tudo numa
única transação. O pacote final não deve depender de uma versão futura do próprio
Atualizador que a RC1 não consiga obter; entregar sua capacidade de migração na ISO.

**Fase B — identidade:** publicar release estável oficial do repositório planejado
`mainuan/mainuan-release`, com `mainuan-release_2027.1_all.deb` e digest SHA-256
verificável pela API. A RC pode ser um prerelease/artefato da construção da ISO;
o canal normal ignora prereleases. Não tornar a RC estável para contornar esse filtro.

No momento autorizado de publicar a final, incluir em packages.txt:

```text
mainuan-release
```

E, por exemplo, em message.txt:

```text
O Mainuan 2027.1 final está disponível!

Após receber os componentes obrigatórios, conclua a atualização da sua RC1
sem reinstalar o sistema.
```

São exemplos futuros: os dois arquivos atuais não foram alterados. Não há JSON,
chave de catálogo, serviço novo ou ação privilegiada específica no Atualizador.
Mantêm-se HTTPS, SHA-256, conferência de control, simulações, confirmação explícita,
PolicyKit nativo e progresso. SHA-256/HTTPS não equivalem a assinatura APT.
Se faltarem componentes, bloquear a promoção sem alterar a identidade; a mensagem
de erro deve identificar o requisito e permitir tentar novamente depois.

## 7. Plano de ensaio isolado — ainda não executado

Usar rootfs descartável para empacotamento/scripts e VM Mainuan com snapshot para
PackageKit, boot e serviços. Usar pacotes fictícios de dados para injetar falhas.

| Cenário | Resultado obrigatório |
| --- | --- |
| Instalar a ISO RC1 | mainuan-release RC configurado; identidade RC ativa e base 26.04 preservada |
| Atualizar base-files antes/depois da promoção | Override Mainuan preservado; link do fornecedor atualizado no destino desviado; nenhum prompt/conflito em lsb-release |
| Descompactar pacote final sem configurar | Identidade continua RC1 |
| Componentes obrigatórios ausentes, antigos ou incompletos | Falha; identidade RC1 preservada |
| Cancelar download/autorização ou alterar hash/control | Nenhuma promoção |
| Instalação final com todos os requisitos | Uma promoção atômica, pacote configurado, identidade final confirmada |
| Falha de componente na fase A | Não promover; reconhecer resultados parciais sem alegar rollback global |
| Disco cheio, symlink inesperado ou diversion de terceiro | Abortar preservando identidade e arquivos existentes |
| Corte antes/depois da troca de active | RC ou final completa, nunca perfil truncado; reconfiguração idempotente |
| Reinstalar final e repetir postinst | Revalidar requisitos; sem duplicar diversion ou notificações |
| Pacote final instalado por outro meio | Reconhecer recebido após confirmar identidade ativa |
| Usuário novo/histórico limpo já na final | Não reapresentar a mesma promoção |
| Remoção/purge e abort-install/abort-upgrade | Restaurar fallback Ubuntu quando apropriado; nenhum link quebrado ou remoção da diversion em upgrade normal |
| Tentar RC sobre final ou instalar em Kubuntu genérico/base errada | Bloquear a promoção/regressão indevida; não mudar a identidade |
| Sessão Live | Nenhuma consulta automática ou instalação pelo Atualizador |
| Logout/login e reinicialização | Identidade final consistente; Plasma, Discover, APT, PolicyKit e Gestão de Drivers funcionam |

Um ensaio de pacote isolado não comprova integração de boot/Plasma. Reinstalar
mainuan-release não repara componentes removidos nem substitui restauração por
snapshot. Após remoção deliberada/forçada de componentes finais, a certificação
da edição deixa de valer: isso exige reparo e nova verificação, não um downgrade
silencioso ou uma promessa de vigilância contínua por este pacote.

## 8. Critérios para construir e liberar a ISO RC1

Antes da publicação da RC1, exigir:

1. Inventário do rootfs real e validação do contrato não conffile de /etc/os-release.
2. mainuan-release RC1 configurado, sem branding por sed/cópia sobre base-files.
3. Contrato de identificação e backend capazes de confirmar promoção, incluídos
   na ISO e testados com um pacote final **fictício**, sem publicar final real.
4. Definição controlada do que será obrigatório na final e da forma de distribuição
   desses componentes, inclusive dependências; evitar uma promoção inalcançável
   pelo backend conservador atual.
5. Matriz de instalação, falha, base-files, recuperação e reinstalação aprovada;
   VM preservando usuários/dados e fontes Ubuntu 26.04.
6. Verificação de ausência de nova promoção em uma máquina já final, inclusive
   com estado local limpo. Guardar logs, versões e hashes como evidência da ISO.

**Pendências atuais:** o construtor/rootfs da ISO RC1 e a lista final de requisitos
não foram disponibilizados; o pacote, seus scripts e os ajustes de backend ainda
não existem. Não há migração homologada ou prontidão de publicação declarada.
Nesta etapa foram realizados somente inventário/leitura de código, consulta das
especificações e comparação Debian das versões. Interface, código executável,
packages.txt, message.txt, configuração do sistema e workflows foram preservados.
