# Atualizador de Recursos do Mainuan

Para o primeiro teste prático em VM com snapshot, consulte
[a versão candidata 0.2.0 RC1 e o modo `--homologacao-github`](docs/v0.2.0-rc1.md).
Esse modo lê `packages.txt` e `message.txt` do GitHub, instala exclusivamente o
aplicativo Gestão de Drivers 1.0 pelo PackageKit/PolicyKit e não configura produção.

Canal oficial para **conhecer novidades antes de instalar**. Python 3 com
**PyQt6 Widgets**, destinado ao Mainuan baseado no Kubuntu 26.04 LTS / Plasma 6.

O aplicativo apresenta lançamentos de um catálogo JSON assinado, seus programas,
versões e a matéria explicativa. A instalação é voluntária e usa
**PackageKit por QtDBus e PolicyKit**. O atualizador APT/Flatpak existente continua
responsável pelas atualizações gerais.

A [candidata local de homologação](docs/versao-candidata.md) reúne o estado do Git,
os comandos de commit/push para futura autorização e os critérios de aprovação
em VM. A produção permanece desativada.

A [interface clássica consolidada](docs/consolidacao-interface.md) já é usada
pelo aplicativo principal e pelo modo `--demo`: beija-flor à esquerda, mensagem
e programas do catálogo à direita. Histórico, detalhes técnicos e verificação
manual ficam no menu. A ilustração acompanha o pacote Debian.

## Experimentar sem modificar o sistema

Dependências de desenvolvimento: `python3-pyqt6`, `python3-cryptography` e
`python3-apt`, fornecidas pela distribuição. Use o Python do sistema:

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario parcial
```

Cenários: `novo`, `visualizado`, `adiado`, `instalado`, `parcial`, `indisponivel`,
`incompativel`, `erro`, `cancelado`. O modo de demonstração simula inclusive a
confirmação, a autorização e o progresso. Não cria transporte D-Bus, não consulta
APT/rede e mantém os estados em memória. O botão da matéria abre o navegador.

Para exercitar também a assinatura com chaves **descartáveis**:

```bash
/usr/bin/python3 tools/dev-catalog.py /tmp/mainuan-catalogo-teste
/usr/bin/python3 tools/catalog.py verify /tmp/mainuan-catalogo-teste/catalog.json \
  --config /tmp/mainuan-catalogo-teste/config.json
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo \
  --test-catalog /tmp/mainuan-catalogo-teste/catalog.json \
  --test-config /tmp/mainuan-catalogo-teste/config.json
```

Escolha um diretório novo; a ferramenta recusa sobrescrever um existente. As
opções de catálogo/configuração locais são aceitas somente com `--demo`.

## Infraestrutura oficial e ativação

Comece pelo [guia de configuração inicial](docs/configuracao-inicial-producao.md),
voltado ao responsável pela distribuição. O guia separa preparação única,
lançamentos cotidianos e autorização para o primeiro piloto, com comandos e
resultados esperados. Inclui [homologação real em VM](docs/homologacao-producao-vm.md)
e [auditoria da infraestrutura](docs/preparacao-infraestrutura-relatorio.md).

O caminho reservado é:
`https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json`.
A assinatura fica em `novidades.json.sig`. As matérias podem apontar somente para
`https://github.com/mainuan/`, incluindo páginas de repositórios e notas de lançamento.
A validação verifica o **caminho**, além do domínio, e rejeita travessia e
codificações ambíguas.

**A produção permanece desativada até a equipe provisionar a chave pública e
publicar um catálogo assinado.** `catalogo/novidades.json` é uma estrutura vazia,
ainda sem assinatura. Nenhuma chave oficial foi inventada. A configuração em
`/etc/mainuan/atualizador-recursos.json` é administrada pela distribuição, e não
pelo manifesto. A demonstração funciona mesmo sem configuração de produção.

Após essa preparação inicial, publicar novidades exige editar somente
[packages.txt](packages.txt) (nomes de repositórios Mainuan) e
[message.txt](message.txt) (mensagem livre). A automação lê os `.deb` das releases
aprovadas, congela versões/hashes, gera um repositório APT assinado e publica o
catálogo assinado. Não há JSON ou comando de assinatura na rotina editorial.
Alterar apenas a mensagem preserva os programas aprovados. Veja
[publicação pelos dois arquivos](docs/publicacao.md).

## Comportamento

- Janela nativa em português com **Conhecer novidades**, **Instalar novidades** e
  **Agora não** e lista simples de recursos; versões e histórico acessíveis no menu.
- Autostart KDE: primeira verificação após 60 segundos, depois a cada hora. Sem
  verificações em sessão Live; nenhuma operação bloqueia o início do Plasma.
- Visualização, adiamento por 24 horas e situação dos pacotes têm estados
  separados por identificador/versão. Fechar uma janela já apresentada não a
  repete; **Agora não** agenda sua reapresentação. O menu permite acesso manual.
- Pacotes já configurados na versão mínima ou superior aparecem como **Já
  recebido**, mesmo se vieram do atualizador tradicional. Não são reinstalados.
- Antes da confirmação, APT somente leitura e PackageKit verificam versões,
  arquiteturas, origens e dependências; a operação é novamente validada antes
  de instalar. Conclusão depende de `Finished` e de nova leitura do estado dpkg.
- Sem rede, um cache com assinatura e validade ainda verificáveis permite
  consulta. A instalação permanece desabilitada; dados inválidos não substituem
  um catálogo confiável. Sem cache válido, a interface informa o erro.
- Sem estilos ou cores fixas na interface: usa a paleta do Plasma, ícones de
  tema e Widgets nativos. Nenhuma chamada X11 é necessária.

## Testar e empacotar

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
bash build-package.sh
# Alternativa usando o empacotamento Debian completo:
dpkg-buildpackage -us -uc -b
```

O primeiro construtor gera `dist/mainuan-atualizador-recursos_0.2.0_all.deb`, sem
root. O workflow testa em Ubuntu 26.04, usa debhelper e disponibiliza um artefato
`.deb`. Não cria tags nem releases. Os testes não instalam pacotes.

[Arquitetura e análise do PR #1](docs/arquitetura.md) ·
[Publicação do catálogo](docs/publicacao.md) ·
[Testes e homologação](docs/testes.md) ·
[Relatório de entrega](docs/relatorio.md)

Licença: GPLv3, preservando a licença do projeto original TigerOS. O Gestão de
Drivers é referência de arquitetura, sem dependência entre os aplicativos.

## Homologação antes da produção

A [auditoria e homologação local](docs/homologacao.md) registra as correções,
92 testes automatizados, capturas em Wayland/Dream, paletas clara/escura e ciclo
Debian isolado. As pendências de uma VM Mainuan estão separadas. A produção
permanece desativada até a chave pública oficial e o catálogo assinado serem
provisionados por decisão dos responsáveis.


## Integrações reais e preparação da VM

A [etapa final de homologação](docs/vm-final.md) identificou a instalação física
Mainuan disponível e a ausência de snapshot/VM. Foram aprovados 101 testes,
consulta/simulação no PackageKit real, timer de 60 s e paletas BlurGlassy reais
em Wayland. Instalações autorizadas e aprovação da RC continuam pendentes da VM.
O roteiro inclui um kit descartável com pacotes de dados e repositório assinado;
a produção permanece desativada.

Para o primeiro ensaio real com o pacote oficial Gestão de Drivers 1.0, use o
[kit e roteiro específico](docs/primeiro-teste-drivers-vm.md). Ele exige snapshot,
limita a operação à instalação do aplicativo e recusa mudanças em dependências.

## Publicação simplificada

O [relatório desta etapa](docs/publicacao-simples-relatorio.md) descreve a análise
do TigerOS, a automação, 129 testes e a demonstração completa com três programas
fictícios. `publication.toml` contém apenas a configuração inicial controlada;
o workflow de publicação depende de habilitação explícita e Secrets protegidos.
Nenhuma chave oficial ou source APT foi instalada nesta entrega.

```bash
/usr/bin/python3 tools/demo-publication.py --output /tmp/mainuan-publicacao-ficticia
/usr/bin/python3 tools/probe-publication.py /tmp/mainuan-publicacao-ficticia \
  --output /tmp/mainuan-publicacao-ficticia/apt-real.json
```

O primeiro comando não usa rede; o segundo valida o APT em sandbox sem rede,
com host somente leitura, e exige `bubblewrap`. Ambos usam chaves descartáveis
e não instalam pacotes. Veja no guia como abrir essa publicação com `--demo`.
