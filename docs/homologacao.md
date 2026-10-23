# Homologação do Atualizador de Recursos — 22/10/2026

Este relatório registra a segunda rodada. A [etapa de integrações reais](vm-final.md)
traz 101 testes, correção adicional da detecção Live e o roteiro de VM pendente.

**Resultado: auditoria e validação local concluídas; ativação de produção não
autorizada.** A configuração conserva `keys: {}` e o catálogo oficial continua
sem assinatura. Nenhuma chave de produção, commit, push, merge, tag ou release
foi criado. Nenhum pacote do host foi instalado, removido ou atualizado.

## Problemas encontrados e corrigidos

| Componente | Problema | Correção |
| --- | --- | --- |
| Aceitação do catálogo | A sequência só era persistida depois da consulta APT; falhas nessa etapa atrasavam a proteção contra retrocesso. | Persistir a sequência autenticada antes do cache e do APT; aplicar o mesmo controle no cache offline. |
| Estado local | Falha de gravação deixava a memória diferente do arquivo; validações com `assert` eram desativadas por `python -O`. | Validação explícita, alterações protegidas por lock, recuperação da memória em falhas e sincronização do arquivo e diretório. |
| Persistência | Reabrir uma novidade já visualizada regravava o arquivo sem mudança. | Não gravar estados idênticos, reduzindo sincronizações em disco. |
| URLs e dados locais | Espaços podiam ser normalizados de maneira diferente por Python e Qt; arquivos locais eram lidos inteiros antes do limite. | Rejeitar espaços em URLs, limitar versões a 128 caracteres sem revisão vazia e limitar a leitura de configuração, estado e cache. |
| Dependências | Estado incompleto de uma dependência não era bloqueado; consulta por nome podia observar outra arquitetura. | Exigir configuração completa e consultar a arquitetura exata dos efeitos simulados. |
| PackageKit | O estado 29 era exibido como autorização; atualizações parciais de propriedades perdiam status/progresso. | Autorização corresponde a 31; bloqueio a 30; reter propriedades ainda válidas. |
| Instância única | Socket não tolerava mensagem fragmentada; abertura manual podia conservar dados antigos. | Acumular o comando e solicitar nova consulta na ativação manual. |
| Autostart | Se uma instância manual abrisse antes do autostart, fechar a janela encerrava as verificações da sessão. | O autostart converte a instância existente em processo de sessão, sem abrir outra janela. |
| Consulta com APT indisponível | Um catálogo válido ficava oculto quando falhava a leitura dos pacotes. | Preservar a apresentação editorial e informar a falha; instalação desabilitada. |
| Conteúdo vazio/erros | Catálogo vazio conservava título antigo; exceção sem texto podia ser confundida com sucesso do worker. | Limpar os detalhes e usar o nome da exceção como mensagem mínima. |
| Interface | Em 640×480, histórico lateral escondia colunas; descrições e confirmação longas ampliavam a janela. | Seletor compacto de histórico, ações em duas linhas, textos e confirmação com rolagem. |
| Demonstração | Apenas dois programas e marcador global de instalação. | Três programas, artigo fictício e recebimento por nome/versão, permitindo testar um lançamento posterior. |

Não foram adicionados gerenciador geral de updates, repositórios, helper root,
comandos remotos ou dependência do Gestão de Drivers.

## Testes automatizados e validações executadas

**92 testes passaram.** Comando:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

A suíte cobre assinatura antes do processamento, alteração dos bytes, chaves
inválidas e rotação/revogação, validade, campos desconhecidos, URLs e caminhos,
redirecionamento para outra conta, retrocesso online/offline, falha na persistência,
validação com `python -O`, versões Debian, retenções, configuração incompleta,
dependências multiarch, simulação e alterações após confirmação. Usa sinais
fictícios para falha, cancelamento, perda do daemon e concorrência APT.

Testes com **processos reais** validaram instância única, comandos fragmentados,
ativação manual com nova consulta, recuperação de lock após processo encerrado
e a ordem manual → autostart → fechar janela, preservando a verificação da sessão.
Esses processos usam estado temporário e substituem a consulta de catálogo.

Uma consulta real `Resolve` via QtDBus retornou identificadores e `Finished` com
sucesso. A leitura APT reconheceu o Python instalado como **Já recebido**. Esse
ensaio é somente leitura; nenhum `InstallPackages` real foi enviado.

O contrato de estados e efeitos foi conferido com os XMLs instalados e o upstream
[PackageKit 1.3.4](https://github.com/PackageKit/PackageKit/blob/v1.3.4/lib/packagekit-glib2/pk-enum.h),
[backend APT](https://github.com/PackageKit/PackageKit/blob/v1.3.4/backends/apt/apt-job.cpp).

### Jornada de experiência

| Cenário | Resultado automatizado |
| --- | --- |
| Primeira novidade, com três programas | Janela apresentada; visualização registrada; pacotes pendentes. |
| Conhecer novidades | URL enviada a QDesktopServices; navegador interceptado no teste. |
| Agora não | Janela oculta e prazo persistido. |
| 24 horas | Sem notificação até 86.399 segundos; elegível aos 86.400 segundos. |
| Abertura manual durante o prazo | Histórico e botões acessíveis; prazo mantido. |
| Preparar instalação | Plano simulado e confirmação com programas e dependências. |
| Cancelamento | Sem confirmação de sucesso; recursos continuam pendentes. |
| Falha | Mensagem de falha; recursos continuam pendentes. |
| Conclusão | Versões simuladas conferidas; pacotes marcados como recebidos. |
| Publicação posterior | Nova sequência e novo anúncio apresentados; estado anterior preservado. |

Visualizar ou abrir o artigo não marcou recursos como instalados. A contagem de
24 horas usa relógio controlado, sem aguardar um dia real. A abertura efetiva do
navegador padrão por clique do usuário ainda integra a matriz manual.

## Homologação visual e consumo

O ambiente disponível tinha KDE em **Wayland**, estilo Qt **Breeze**, esquema
ativo **DreamBrownDarkColor**, tela de 1366×768. Capturamos apenas as janelas do
aplicativo, sem alterar o tema ou a resolução do desktop.

| Ensaio | Resolução lógica / escala | Resultado | Maior PSS observado | Maior RSS observado |
| --- | --- | --- | --- | --- |
| Wayland, tema ativo | 960×600 / 100% | Demo, confirmação, progresso e conclusão | 67,5 MiB | 168,6 MiB |
| Wayland, tema ativo | 640×480 / 100% | Ações dentro da janela; fluxo completo | 54,3 MiB | 162,4 MiB |
| Qt offscreen, paleta clara | 640×480 / 100% | Três programas e ações visíveis; fluxo completo | 33,4 MiB | 76,4 MiB |
| Qt offscreen, paleta escura | 640×480 / 100% | Texto legível e fluxo completo | 32,3 MiB | 75,2 MiB |
| Qt offscreen, paleta escura | 800×600 / 150% | Layout e confirmação com escala | 41,5 MiB | 82,7 MiB |

Medições de `/proc/self/smaps_rollup`; PSS reparte memória compartilhada e varia
com outros processos. O pico RSS do processo também é registrado em `VmHWM`.
A janela ficou pronta em aproximadamente 0,09–0,25 segundo nestes ensaios, com
catálogo e pacotes fictícios. Isso não mede download, leitura real de APT, nem o
consumo total de um desktop limitado a 2 GB. Não equivale à aprovação desse hardware.

As paletas clara/escura foram alteradas **somente no processo de ensaio**. O
aplicativo continua usando o tema Qt ativo, sem stylesheet ou cores fixas. Dream
ativo foi inspecionado; Blur-Glassy, outros variantes Dream e composição/transparência
com diferentes escalas ainda exigem inspeção na VM-alvo.

`Conhecer novidades` recebeu ícone e texto em negrito. A instalação mantém um
botão explícito e confirmação cujo padrão é **Cancelar**. O diálogo mostra a
operação completa com rolagem. Descrições/erros extensos também têm rolagem.
Em telas estreitas, o histórico vira um seletor nativo; a lista de pacotes mantém
rolagem para temas com fontes maiores.

Capturas e métricas estão em `dist/homologacao/`, inclusive `novidade.png`,
`confirmacao.png`, `progresso.png`, `concluido.png` e `resultado.json` por cenário.

## Homologação Debian em ambiente isolado

O `.deb` foi instalado com dpkg em uma raiz descartável, sob namespace de usuário
e bubblewrap, com o host montado somente para leitura e rede desabilitada.
As dependências foram satisfeitas **como metadados**, a partir de uma cópia da
base dpkg do host. Isso valida o ciclo do pacote, não uma instalação completa
em uma imagem Mainuan inicializada.

Passaram: instalação, validação das entradas de menu/autostart instaladas,
execução do launcher instalado com `--version`, fluxo completo do launcher
instalado com `--demo`, renderização Qt do SVG, remoção e reinstalação. Uma
alteração local no conffile e um arquivo no estado do usuário permaneceram
preservados. A produção permaneceu desativada. O log é `dist/homologacao/debian/dpkg.log`.

## O que ainda exige VM real com Plasma/Wayland

- Instalar o `.deb` e conferir presença no menu, busca, ícone e agrupamento da janela.
- Login/logout reais, autostart após 60 segundos, consulta horária, suspensão/retomada,
  ordem manual/autostart, recuperação de processo interrompido e acesso pelo menu.
- Iniciar pela mídia Live e confirmar ausência de acesso à rede/APT; o código Live
  foi testado automaticamente, não em uma mídia inicializada nesta etapa.
- Matéria real no navegador padrão, teclado, foco, leitor de tela e traduções Qt.
- Dream e Blur-Glassy claros/escuros, composição, fontes maiores e escala real de
  150/200%; não trocar o tema global enquanto houver trabalho não salvo.
- VM limitada a **2 GB de RAM**, avaliando consumo do desktop, pressão de memória
  e resposta durante download/instalação real.
- Autorizar, negar e cancelar **PolicyKit real**, com repositório APT de homologação
  autenticado. Validar pacotes ausentes, antigos, já recebidos e dependências reais.
- Executar concorrência com Discover/APT e alterar candidatos durante a confirmação
  e durante a espera por autorização. Conferir bloqueios, mensagens e estado dpkg.
- Falhas reais de download/dpkg, perda do daemon e resultados parciais; nunca
  declarar conclusão apenas pelo progresso ou pela resposta inicial do método.
- Remover/reinstalar na VM com dependências completas e configuração pública de
  homologação já alterada, conferindo os conffiles e o histórico do usuário.

O PackageKit não oferece ligação atômica entre nossa simulação e o commit.
Revalidamos o plano e os efeitos, mas alterações durante autorização/concorrência
continuam sendo uma limitação. Não há rollback automático. Esse risco permanece
registrado; os ensaios simulados não homologam transações reais.

## Reproduzir interface e pacote

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario cancelado
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario erro
```

O artigo padrão do demo usa um domínio fictício; o ensaio automatizado intercepta
o navegador. Para conferir a aparência e gerar métricas/capturas reproduzíveis:

```bash
QT_QPA_PLATFORM=wayland /usr/bin/python3 tools/homologate-gui.py \
  --palette active --size 640x480 --output dist/homologacao/wayland-640
QT_QPA_PLATFORM=offscreen /usr/bin/python3 tools/homologate-gui.py \
  --palette light --size 640x480 --output dist/homologacao/claro-640
QT_QPA_PLATFORM=offscreen /usr/bin/python3 tools/homologate-gui.py \
  --palette dark --size 640x480 --output dist/homologacao/escuro-640
```

O modo nativo depende de uma sessão Wayland acessível. O roteiro usa a mesma
janela e backend do demo; não chama o gerenciador de pacotes. Para o ciclo dpkg
isolado, é necessário `bubblewrap`, namespace de usuário disponível e as
bibliotecas Qt já presentes no host:

```bash
bash build-package.sh
/usr/bin/python3 tools/homologate-deb.py \
  dist/mainuan-atualizador-recursos_0.2.0_all.deb --output dist/homologacao/debian
```

Se namespaces não estiverem disponíveis, use a VM; o roteiro não oferece fallback
que escreva no host. Ele também recusa pacotes com scripts de mantenedor, pois a
raiz mínima não equivale a um sistema inicializado.

## Ativação segura futura

O processo de geração controlada, custódia, distribuição da chave pública,
assinatura, validação, limites contra retrocesso e substituição/revogação de
chaves está em [publicacao.md](publicacao.md). Conclua as pendências da VM,
provisione a chave pública por configuração confiável e publique JSON/assinatura
somente após autorização. Nenhum desses passos de produção foi executado.
