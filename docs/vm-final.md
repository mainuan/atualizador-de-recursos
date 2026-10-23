# Homologação final: resultado local e roteiro de VM — 22/10/2026

Para uma nova execução antes da primeira publicação, use o
[roteiro atualizado de VM](homologacao-producao-vm.md), com catálogo fixado por
versão/arquitetura/hash e APT HTTPS local. Este documento conserva as evidências
históricas da homologação anterior.

**A homologação final com instalações reais não está aprovada.** Foram concluídos
os ensaios possíveis sem modificar os pacotes do computador disponível. A
produção continua sem chave pública e sem catálogo assinado. Não foram criados
commit, push, merge, tag ou release.

## Ambiente identificado e condição de restauração

- Instalação física **Mainuan 2026 LTS**, baseada em resolute, kernel 7.0.0-38.
- Plasma/KWin **6.6.6**, Wayland, Qt Wayland 6.10.2, PackageKit 1.3.4,
  polkitd 127 e agente KDE 6.6.4.
- Aproximadamente **11,5 GiB de RAM**, raiz ext4. Não é uma VM de 2 GB.
- `/dev/kvm` existe, mas não foram encontrados hypervisor executável, VM ou
  imagem Mainuan nos locais de teste examinados.
- Timeshift está instalado, mas não há configuração nem snapshot nos locais
  padrão examinados. Não existe restauração verificada para uma transação no host.

Por essa condição, **não foram executados InstallPackages sem SIMULATE, instalação
APT, instalação global do aplicativo ou alterações de PolicyKit/APT no host**.
Não consideramos uma cópia da base dpkg um backup suficiente para restaurar um
sistema real. Os ensaios de arquivos/índices utilizaram raízes descartáveis e,
quando aplicável, bubblewrap com o host somente para leitura.

A identidade efetiva da imagem é `ID=ubuntu`, `VERSION_ID=2026`, arquitetura
`amd64`. Não publique compatibilidade `mainuan/26.04` por suposição; os campos
precisam corresponder à imagem efetiva. Não foi alterado `/etc/os-release`.

## Resultados executados

| Ensaio | Resultado e alcance |
| --- | --- |
| Suíte automatizada | **101 testes aprovados**, incluindo regressões de Live e os testes anteriores de estado, catálogo, transações e instância única. |
| Identificação do host | Reconhecido como instalação normal; sem parâmetros de boot Live e com raiz ext4. |
| PackageKit real, Resolve | `hello` encontrado no Ubuntu confiável; versão e arquitetura conferidas. |
| PackageKit real, SIMULATE | Simulação de `hello` concluída e efeitos validados; o pacote permaneceu ausente antes/depois. Nenhuma instalação real solicitada. |
| PackageKit real, falha | ID inexistente em transação SIMULATE retornou o erro 8, sem confirmação de sucesso. |
| Consulta de autorização | `CanAuthorize(package-install)` retornou **3: interativa**. Isso não executa nem aprova o diálogo de autenticação. |
| Concorrência observada no host | PackageKit estava sem transações ativas e `Locked=false`; não foi provocada uma operação mutante para criar concorrência. |
| Lock APT isolado | Lock real, pertencente a um processo do teste, fez o APT retornar código 100 e identificar seu detentor. A base de status descartável permaneceu inalterada. Não equivale a concorrência real do aplicativo com Discover. |
| Catálogos do kit | Duas edições com assinatura descartável validadas, sequência 1/2; chave privada de assinatura descartada. |
| Repositório do kit | Índice assinado validado pelo APT real em configuração isolada; três candidatos 1.0 reconhecidos como confiáveis, solver aprovado. Sem instalação. |
| TLS do kit | Certificado local verificado com OpenSSL em modo estrito e hostname esperado. A CA não foi instalada no host. |
| Entrada KDE | `kbuildsycoca6 --menutest` incluiu `System/ org.mainuan.Recursos.desktop` usando o pacote extraído em prefixo XDG isolado. O menu global não foi alterado. |
| Timer do launcher extraído | Primeira consulta medida aos **60,353 s**, janela oculta e rede bloqueada. Falta da chave foi tratada; intervalo horário configurado em 3.600.000 ms. Não foi observado um login novo ou aguardada uma hora. |
| BlurGlassy claro/escuro | Demo completo em Wayland/Breeze, 640×480, com os arquivos reais `.colors` aplicados somente ao processo. Cor de janela conferida com o arquivo de esquema. |

A simulação usou `ONLY_TRUSTED | SIMULATE` e um transporte de ensaio que rejeita
qualquer pedido InstallPackages sem SIMULATE. Não se contornaram locks. O pacote
`hello` não foi instalado. O progresso observado pertence à resolução/simulação,
**não** a uma instalação autorizada.

A consulta `CanAuthorize=3` indica possibilidade de desafio interativo; não prova
que o agente mostrou a janela. Cancelar senha, autorizar, instalar realmente e
verificar ausência de reinstalação depois de um commit real permanecem pendentes.
O contrato foi conferido com o XML instalado de PackageKit e seus
[enums oficiais](https://github.com/PackageKit/PackageKit/blob/v1.3.4/lib/packagekit-glib2/pk-enum.h).

### Senhas

A revisão do aplicativo não encontrou campo de senha, leitura de senha por stdin,
PAM, sudo ou pkexec. QtDBus envia autorização interativa ao PackageKit e o agente
PolicyKit fica responsável pela autenticação. Nenhuma senha foi solicitada,
capturada ou armazenada nestes ensaios. A verificação dinâmica do diálogo real
deve ser feita na VM, sem gravar a digitação ou incluir credenciais nos logs.

## Falha corrigida: falso positivo de Live

A regra anterior considerava `/cdrom/casper` isoladamente e chamava qualquer
falha de leitura do cmdline de Live. Uma ISO montada depois do login poderia
bloquear uma instalação normal.

A implementação agora diferencia **instalada, Live e desconhecida**. Parâmetros
`boot=casper`/`boot=live` são evidência direta. O fallback exige raiz overlay com
evidências ativas de ambiente Live. Mídia montada sozinha não altera a classificação.
Raiz normal ext4 continua instalada mesmo com cmdline indisponível. Evidência
insuficiente gera estado desconhecido, com consulta/instalação bloqueadas e
mensagem própria, sem chamar a sessão de Live.

Autostart Live/desconhecido encerra antes de criar QApplication ou consultar a
rede; abertura manual não constrói a janela de recursos. Isso foi testado com
evidências controladas. **A inicialização de uma ISO Mainuan real ainda não foi
executada.** O modo demo é explicitamente simulado e não realiza instalações.

## Memória e resposta com leitura APT real

Ensaio em Wayland, com catálogo local autenticado. Apenas o transporte remoto foi
substituído; o worker leu o cache APT verdadeiro. PackageKit ficou bloqueado no
ensaio de memória e o botão de instalação permaneceu desabilitado.

| Estado | PSS | RSS |
| --- | --- | --- |
| Repouso inicial, processo de sessão oculto | cerca de 54–57 MiB | cerca de 156 MiB |
| Amostra durante consulta APT | 89,4 MiB | 232,8 MiB |
| Após consulta e estabilização | 74,2 MiB | 179,7 MiB |

Pico de RSS registrado por `VmHWM`: **236,6 MiB**. A consulta levou **422 ms**.
Maior intervalo do timer de interface: **303 ms**, com instrumento configurado
para 100 ms. Não houve travamento ou atraso de segundos. Em cinco segundos de
repouso estabilizado foram consumidos 0,053 s de CPU, aproximadamente 1,1% de um
núcleo, incluindo instrumentação. A amostragem PSS é influenciada por bibliotecas
compartilhadas e outros processos; o pico de RSS é informado separadamente.

Esses números não incluem todo o desktop e não aprovam uma VM de 2 GB. A leitura
APT aumenta a memória temporariamente; o teste da imagem completa sob pressão
de RAM continua obrigatório.

## Limites da integração visual observada

Os esquemas BlurGlassy reais foram carregados em configuração temporária privada,
sem trocar o tema do desktop. O compositor permaneceu com a decoração ativa
Lavanda/Dream. A composição, transparência e decoração completas do tema
Blur-Glassy, bem como o agrupamento no lançador após instalação global, precisam
de validação na VM.

Ao executar o launcher apenas extraído, o portal do host informou que não conhece
o App ID `org.mainuan.Recursos`. É uma limitação observada do prefixo isolado:
a entrada não está instalada no ambiente do portal global. O teste de menu por
prefixo passou, mas isso **não comprova** o registro completo após instalar o `.deb`.
A ausência desse aviso deverá ser conferida na VM.

## Kit descartável para os ensaios que faltam

Artefatos em `dist/homologacao-final/kit-vm/`:

- `repo-v1/` e `repo-v2/`: repositórios APT assinados com uma chave GPG descartável.
- Três pacotes `mainuan-homologacao-alpha`, `-beta`, `-gamma`, versões 1.0/2.0.
  Cada pacote contém **somente um arquivo de texto** em `/usr/share/mainuan-homologacao/`.
  Não possui executáveis, scripts de mantenedor, dependências ou autostart.
- `edicoes/`: duas edições assinadas do catálogo; `site/catalog/` começa na edição 1.
- `config-homologacao.json`: URL local `https://homologacao.mainuan.test/...`,
  chave pública descartável e matérias limitadas a `https://github.com/mainuan/`.
- `tls/`: CA pública de teste, certificado e chave do servidor local; não são
  credenciais de produção. A CA privada e as chaves privadas de assinatura do
  repositório/catálogo foram descartadas após gerar o kit.
- `servir-catalogo.py`: servidor HTTPS somente em **127.0.0.1:443**, sem CGI.
- `kit.json`: validade e impressão digital da chave pública do repositório.

A validade é de **dois dias**, expressa em UTC em `kit.json`. Gere um kit novo se
expirar. O kit não configura APT, não instala CA e não muda a configuração do host.
Todos os comandos administrativos abaixo são **somente para a VM restaurável**.

### 1. Preparar e provar restauração

1. Disponibilize uma VM Mainuan instalada, Plasma/Wayland, usuário normal com
   agente PolicyKit e **2 GiB de RAM**. Registre versão, arquitetura e resolução.
2. Desligue a VM e crie snapshot/checkpoint no hypervisor, incluindo todos os
   discos mutáveis. Registre nome e identificador; não use apenas backup de `/var/lib/dpkg`.
3. Prove a restauração com um arquivo canário inofensivo: crie-o na VM, restaure
   o checkpoint e confirme sua ausência. Recrie um checkpoint limpo antes da preparação.
4. Copie o `.deb` e o kit para a VM. Não comece a etapa administrativa se a
   restauração falhar. Não substitua o checkpoint por uma promessa de reinstalação.

### 2. Configurar somente a infraestrutura de homologação na VM

Execute de um terminal dentro da VM, ajustando os caminhos de origem:

```bash
sudo apt install ./mainuan-atualizador-recursos_0.2.0_all.deb
sudo install -d -m 0755 /opt/mainuan-homologacao
sudo cp -a ./kit-vm/. /opt/mainuan-homologacao/
sudo chmod 0755 /opt/mainuan-homologacao
sudo install -Dm644 /opt/mainuan-homologacao/repo-chave-teste.asc \
  /etc/apt/keyrings/mainuan-homologacao.asc
printf '%s\n' 'deb [signed-by=/etc/apt/keyrings/mainuan-homologacao.asc] file:/opt/mainuan-homologacao/repo-v1 ./' \
  | sudo tee /etc/apt/sources.list.d/mainuan-homologacao.list
sudo install -m644 /opt/mainuan-homologacao/tls/ca-teste.crt \
  /usr/local/share/ca-certificates/mainuan-homologacao.crt
sudo update-ca-certificates
printf '%s\n' '127.0.0.1 homologacao.mainuan.test' | sudo tee -a /etc/hosts
sudo install -m644 /opt/mainuan-homologacao/config-homologacao.json \
  /etc/mainuan/atualizador-recursos.json
sudo apt update
```

A URL de produção nunca entra nessa configuração de teste. Não use `trusted=yes`
nem desabilite validação TLS/assinatura. Em outro terminal da VM, inicie:

```bash
sudo /usr/bin/python3 /opt/mainuan-homologacao/servir-catalogo.py
```

O aplicativo deve ser iniciado **como usuário normal**, pelo menu ou pelo comando
`mainuan-atualizador-recursos`, sem sudo. Confirme que a matéria abre o navegador
padrão. A autenticação administrativa deve pertencer ao agente PolicyKit do Plasma.

### 3. Matriz obrigatória de instalação e falhas

- Confirmar a operação de três pacotes; cancelar a autenticação. Nenhum pacote
  deve ficar instalado e o anúncio deve permanecer pendente.
- Repetir, autorizar e acompanhar o progresso real. Conferir versões e estado
  `install ok installed` no dpkg; abrir novamente e confirmar que não reinstala.
- Verificar atualização: trocar a source para `repo-v2`, executar `sudo apt update`
  e copiar o par `edicoes/novidades-v2.json[.sig]` para `site/catalog/novidades.json[.sig]`.
  Conferir que a edição 2 e a atualização para 2.0 são oferecidas.
- Para falha real de download, antes de instalar 2.0 renomear temporariamente um
  `.deb` em `repo-v2/pool/`, mantendo o índice assinado. O PackageKit deve falhar
  sem indicar sucesso completo. Restaurar o arquivo e repetir; não desligar a confiança.
- Servir a edição 1 depois de aceitar a 2: ela deve ser rejeitada. Alterar um byte
  do catálogo sem reassinar: deve falhar antes de qualquer operação de pacote.
- Interromper apenas o servidor de catálogo para testar indisponibilidade; não
  interromper dpkg no meio de escrita para fabricar uma falha.

Para conferir os pacotes de teste:

```bash
dpkg-query -W -f='${binary:Package} ${Status} ${Version}\n' \
  mainuan-homologacao-alpha mainuan-homologacao-beta mainuan-homologacao-gamma
```

### 4. Concorrência e integração completa

Na VM, restaure o checkpoint apropriado antes de cada variante. Para observar
uma operação APT concorrente de forma previsível, pode-se alongar a instalação
de **um pacote de teste** com um hook local explícito:

```bash
sudo apt-get -o DPkg::Pre-Invoke::='sleep 20' install mainuan-homologacao-alpha
```

Durante esse intervalo, prepare/confirme a instalação no aplicativo. Registre
se espera pelo lock, comunica o impedimento ou pede revisão por alteração do
plano. Depois de ambos terminarem, compare o estado real. Não remova lock files,
não mate o processo APT e não habilite opções que ignorem bloqueios. Uma operação
benigna iniciada pelo Discover deve ser ensaiada separadamente; não dispare uma
atualização geral apenas para criar concorrência.

Confira ainda: menu e ícone após instalação global; decoração e portal sem erro
de App ID; novo login com autostart; ausência de instâncias duplicadas; esquemas
claros/escuros e composição Blur-Glassy; repouso/consulta/instalação com 2 GB;
remoção e reinstalação com configuração local preservada. Inicialize também a
ISO Live e confirme saída do autostart sem rede e ausência de instalação manual.

Ao terminar, exporte apenas logs sem credenciais e restaure o checkpoint limpo.
Isso remove fontes, CA, domínio local, chaves descartáveis, pacotes e estado de
teste. Não transporte a confiança desse kit para uma imagem de produção.

## Evidências e reprodução segura local

Relatórios e capturas: `dist/homologacao-final/`. Exemplos:

```bash
/usr/bin/python3 tools/prepare-vm-kit.py --output /tmp/mainuan-kit-novo
/usr/bin/python3 tools/probe-vm-kit.py /tmp/mainuan-kit-novo --output /tmp/validacao-kit.json
/usr/bin/python3 tools/probe-packagekit-readonly.py --output /tmp/packagekit-leitura.json
QT_QPA_PLATFORM=wayland /usr/bin/python3 tools/probe-consultation-memory.py \
  /tmp/mainuan-kit-novo --output /tmp/memoria.json
QT_QPA_PLATFORM=wayland /usr/bin/python3 tools/homologate-gui.py \
  --scheme /usr/share/color-schemes/BlurGlassyDark.colors --size 640x480 \
  --output /tmp/blur-escuro
```

Os probes locais não oferecem modo de instalação real. A raiz APT do teste de
índice/lock é descartável e não usa os locks do host.

## Recomendação sobre versão candidata

**Não recomendar uma RC homologada para distribuição neste momento.** O código
pode ser usado como candidata interna para a matriz acima, sempre com produção
desativada. Impedimentos para aprovação: snapshot/VM externa disponível,
autenticação cancelada e aceita no agente real, commit e atualização reais,
concorrência com APT/Discover, integração após login, ISO Live e imagem de 2 GB.
Os resultados de simulação, menu isolado e paletas não substituem esses critérios.
A ativação de produção e qualquer publicação continuam dependendo de autorização
explícita após resolver as pendências.
