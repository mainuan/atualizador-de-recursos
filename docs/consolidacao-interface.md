# Consolidação da interface aprovada

A conferência inicial encontrou duas pendências: a janela principal ainda usava
a composição antiga, e o PNG estava somente nos recursos da prévia. Ambas foram
resolvidas sem redesenhar a interface aprovada.

## Integração

`mainuan_recursos.classic.ClassicContent` contém a composição compartilhada por
`mainuan_recursos.gui.Window` e `tools/preview-classic.py`. Foram preservados
proporções, margens, espaçamentos, tamanho padrão 720×420, botões verticais e menu
discreto. Uma captura da prévia compartilhada foi comparada à prévia aprovada,
com os mesmos dados e paleta: os pixels da janela principal permaneceram iguais.
Um teste compara também a geometria dos elementos entre aplicativo e prévia.

| Requisito | Implementação no aplicativo principal |
| --- | --- |
| Ilustração do Mainuan | PNG transparente do beija-flor, com proporção e pintura suave preservadas |
| Mensagem | `Release.summary` do catálogo autenticado, exibido como texto simples |
| Programas | Nomes de `Feature.title`, sem lista fixa de exemplos no aplicativo |
| Conhecer novidades | Abre `Release.article_url` pelo navegador padrão, usando o endereço validado ou a alternativa já calculada pelo leitor do catálogo |
| Instalar novidades | Controlador existente: planejamento, simulação, confirmação, autorização e verificação final |
| Agora não | `State.postpone`, com prazo de 24 horas e fechamento da apresentação |
| Histórico | Lista real de lançamentos e estados, acessível no menu; a seleção troca o lançamento mostrado |
| Informações técnicas | Pacotes, versões mínimas/instaladas/disponíveis, arquiteturas e situação do plano atual |
| Dependências | Operação completa continua disponível na confirmação existente, após simulação pelo PackageKit |
| Verificar novidades | Menu chama o mesmo `Window.reload` existente |
| Português brasileiro | Traduções Qt e correção de rótulos padrão preservadas; botões dos novos diálogos usam Fechar |

Os detalhes técnicos não iniciam transações. Apenas apresentam os metadados já
consultados. Estados indisponível, offline, incompatível, já recebido, erros e
progresso continuam sendo informados. A mensagem redundante de convite foi
retirada da apresentação normal; mensagens operacionais aparecem na própria
área de conteúdo quando necessárias, e o progresso fica acima das ações.

Os diálogos auxiliares também são fechados ao encerrar ou adiar a janela principal,
evitando deixar o histórico aberto após Agora não. A proteção contra fechamento
durante operações permanece ativa. O estado editorial não é usado como prova
de instalação.

## Recurso distribuído

A única cópia canônica da arte está em:

```text
src/mainuan_recursos/assets/mainuan-novidades.png
```

No `.deb`, ela acompanha o módulo:

```text
/usr/lib/mainuan-atualizador-recursos/mainuan_recursos/assets/mainuan-novidades.png
```

O caminho é calculado a partir de `classic.py`, sem depender do diretório atual,
de Downloads, de `tools/` ou de arquivos externos ao pacote. O script de preparação
usado pelos dois construtores inclui explicitamente o PNG. O SHA-256 permanece
`ab18dab7009c85a72bd7b35cdd74f08fcd339bdc3ea0647b987c7f03d53c6c2b`.
Não há alternativa automática para o banner TigerOS.

## Demonstração e reprodução

No checkout, sem instalar ou modificar pacotes:

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario cancelado
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario erro
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo --scenario instalado
```

O modo `--demo` usa o mesmo `Window` e o mesmo componente visual. Somente os dados
e transações são simulados pelo backend de demonstração já existente; o estado
fica em memória. A matéria desse catálogo fictício pode ter endereço de exemplo.
Para ensaiar outros textos e links, use as opções existentes `--test-catalog` e
`--test-config`, com catálogo assinado por chave descartável.

Para repetir os testes e a construção, sem instalar no host:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
dpkg-buildpackage -us -uc -b
```

O construtor debhelper também executa a suíte como verificação obrigatória. O
pacote mantém a versão 0.2.0; este candidato deve ser identificado pelo caminho
da entrega e seu SHA-256, pois não foi criada tag ou release.

## Verificações e evidências

A rodada de consolidação passou em **147 testes**: os 141 anteriores, ajustando
as verificações visuais à nova composição, e seis novos testes de integração.
Os casos novos verificam catálogo autenticado no carregamento normal, recurso
canônico, geometria aprovada, menu real, cancelamento pelo botão de instalação
e fechamento dos diálogos ao adiar. Também foi exercitado o demo completo em
Wayland/Breeze com BlurGlassy claro e escuro, inclusive área reduzida a 150%.

As evidências desta entrega ficam em `dist/consolidacao-interface/`:

- `testes.log`: suíte completa.
- `comparacao-visual.json`: comparação com a prévia aprovada.
- `integridade.json`: hashes dos backends e comparação de métodos existentes.
- `gui-claro/`, `gui-escuro-150/`: demo do aplicativo principal, confirmação,
  progresso e conclusão.
- `construcao.log`: construção Debian e verificações executadas pelo debhelper.
- `debian/resultado-deb.json`, `debian/dpkg.log`, `debian/demo-instalado.png`:
  ciclo de instalação e ensaio do launcher instalado.
- `relatorio-final.md`, `SHA256SUMS`: resultado final e identidade do binário candidato.

`tools/homologate-deb.py` instala o pacote em raiz descartável com bubblewrap,
mantendo o host somente leitura e sem rede. As dependências são representadas
por metadados da instalação existente; isso não substitui instalar dependências
reais numa VM. Durante a execução do launcher e do demo, o checkout é ocultado.
O probe exige que o módulo e a ilustração venham do prefixo instalado e exercita
mensagem/programas, menus, português, artigo sem abrir navegador externo,
cancelamento, progresso simulado, conclusão e adiamento. Também verifica
remoção/reinstalação e preservação de configuração/estado.

Não foi executada instalação real de recursos pelo PackageKit no host.

## O que ainda exige homologação real

Usar a matriz e o [roteiro de VM com snapshot](homologacao-producao-vm.md),
substituindo o `.deb` anterior pelo candidato desta entrega. Permanecem pendentes:

- Instalação efetiva por PackageKit com repositório e chaves descartáveis,
  desafio PolicyKit, cancelamento, falhas e versões dpkg realmente instaladas.
- Concorrência com APT/Discover e bloqueios reais.
- Menu global, cache do ícone e autostart após login real no Mainuan.
- Sessão Live real, instância única no desktop instalado e decorações completas
  de Dream/Blur-Glassy.
- Estabilidade prolongada em VM com 2 GB e resoluções físicas reduzidas.

Sem esses ensaios, o pacote é **candidato interno para homologação**, não versão
aprovada para distribuição. As verificações automatizadas não autorizam ativar
o catálogo de produção.

## Escopo preservado

Controller, PackageKit, planejamento APT, autenticação do catálogo, cache,
histórico/persistência, detecção de sessão, inicialização e publicação não foram
alterados. Na janela, os métodos de carga, artigo, guarda de segurança,
preparação, confirmação, conclusão, progresso e adiamento mantiveram suas árvores
sintáticas originais. As mudanças são composição, apresentação e conexões do menu.

`enabled=false`, `bootstrap=false` e chaves de produção vazias foram preservados.
Não houve criação de chaves oficiais, commit, push, merge ou publicação.
