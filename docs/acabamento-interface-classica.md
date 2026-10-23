# Acabamento da prévia clássica

> Registro da etapa de aprovação visual. A integração posterior ao aplicativo
> principal e ao Debian está documentada em [consolidação da interface](consolidacao-interface.md).

A composição aprovada foi preservada: imagem à esquerda, mensagem e lista à
direita, menu discreto acima e três ações verticais no canto inferior direito.
Esta entrega continua sendo uma prévia local. Não houve commit, push, publicação
ou ativação de produção. Os artefatos `.deb` anteriores não foram substituídos.

## Imagem e compactação

Foi utilizada a variante encontrada em Downloads com o texto **Novidade!**:
`Imagem do ChatGPT 23 de out. de 2026, 00_06_46-2.png`. Ela corresponde à descrição
fornecida: beija-flor-de-fronte-violeta diante de um notebook e símbolo de download.
O arquivo foi copiado, sem edição, para
`tools/preview-classic-assets/mainuan-novidades.png`.

O PNG tem transparência, 1122×1402 pixels e 1.479.582 bytes. O SHA-256 da cópia
é idêntico ao original:
`ab18dab7009c85a72bd7b35cdd74f08fcd339bdc3ea0647b987c7f03d53c6c2b`.
Não se adicionaram fundo, moldura ou efeitos. Qt pinta a imagem inteira com
escala suave e proporção preservada. O banner TigerOS foi removido dos recursos
da prévia, sem alternativa automática para reutilizá-lo. Imagem ausente, inválida
ou sem canal alfa causa erro explícito.

A janela padrão passou de 800×480 para **720×420 pixels lógicos**. A ilustração
passou a se alinhar ao topo da área da mensagem; as margens transparentes da arte
foram preservadas. Foram reduzidos os espaçamentos laterais e entre conteúdo e
ações. As três ações mantêm tamanho igual, espaçamento consistente e alinhamento
à direita. Não há cores fixas, cartões, tabelas ou painéis laterais.

Nomes longos quebram linha. Listas extensas têm rolagem somente no conteúdo,
mantendo os botões acessíveis. A confirmação fictícia também mantém a lista em
área rolável; informações curtas, como Agora não, usam um diálogo menor.

## Abrir e conferir

Na raiz do checkout, dentro da sessão gráfica, sem sudo:

```bash
/usr/bin/python3 tools/preview-classic.py
```

Sem opções, a prévia respeita a paleta e o estilo Qt ativos. Exemplos adicionais:

```bash
/usr/bin/python3 tools/preview-classic.py --long-list --size 640x480

/usr/bin/python3 tools/preview-classic.py \
  --scheme /usr/share/color-schemes/BlurGlassy.colors

/usr/bin/python3 tools/preview-classic.py \
  --scheme /usr/share/color-schemes/BlurGlassyDark.colors

QT_SCALE_FACTOR=1.5 /usr/bin/python3 tools/preview-classic.py --long-list \
  --size 426x288 --scheme /usr/share/color-schemes/DreamCyanLightColor.colors
```

`--scheme` aplica o arquivo `.colors` somente ao processo, com estilo Breeze,
sem alterar o tema global. Os caminhos devem existir no computador usado.
`--long-list` é apenas uma amostra visual com 12 programas fictícios e nomes
extensos. Não existe consulta de disponibilidade ou transação nessa ferramenta.
Instalação, histórico, verificação manual e adiamento continuam demonstrativos.
Conhecer novidades abre a página oficial fixa do repositório após o clique.

## Português brasileiro nos diálogos

A inicialização do aplicativo, a prévia e a ferramenta de homologação gráfica
agora usam `mainuan_recursos.localization.install_pt_br`:

1. Define `QLocale('pt_BR')`, carrega `qtbase_pt_BR.qm` e mantém o `QTranslator`
   referenciado enquanto o aplicativo existir.
2. Prioriza as traduções oficiais do Qt. A dependência Debian existente
   `qt6-translations-l10n` foi preservada.
3. Corrige rótulos padrão que ainda chegam em inglês, como Close, Cancel, Yes e
   No, usando a tradução Qt e, quando ausente, Fechar, Cancelar, Sim e Não.
4. Não altera botões personalizados, seus papéis, valores, sinais ou ações.

Na sessão Wayland, foi reproduzido que a integração KDE pode fornecer **Close**
mesmo com o catálogo Qt carregado. A correção é aplicada antes de exibir caixas
de botões e mensagens padrão. Na prévia, as caixas Fechar também são localizadas
logo após sua criação. O botão de Agora não ficou **Fechar**, com o mesmo
comportamento de rejeitar/fechar a janela.

Os oito novos testes de regressão cobrem catálogo nativo, ausência do catálogo,
rótulos ingleses do tema, prioridade da tradução nativa, mensagens de informação,
aviso, erro e pergunta, textos personalizados, fechamento, cancelamento e sucesso.
Um mock do teste existente de sessão Live foi ajustado do antigo `QTranslator`
para `install_pt_br`; as verificações de bloqueio da janela foram mantidas.

## Resultados

- **141 testes automatizados aprovados**: os 133 existentes e oito novos,
  em 15,097 segundos na execução final.
- **48 verificações de composição aprovadas em Wayland/Breeze**: quatro paletas
  reais (Dream Ciano claro/escuro e BlurGlassy claro/escuro), três referências de
  resolução (640×480, 1024×768, 1366×768), escala 100%/150% e listas de 3/12 itens.
- Verificados imagem contida/com alfa, paleta correspondente, rótulo Fechar,
  botões de tamanho igual e alinhados, ausência de sobreposição com conteúdo,
  quebra de nomes sem corte, acesso a todos os itens por rolagem e ausência de
  rolagem horizontal.
- **10 repetições de encerramento aprovadas** após o ajuste de limpeza descrito
  abaixo. Nenhum pacote foi instalado e nenhuma configuração global foi alterada.

As resoluções foram exercitadas por **simulação da área útil da janela**, no
desktop físico 1366×768 disponível, sem mudar a resolução do monitor. Para cada
referência, a largura lógica é `largura_física / escala`; a altura desconta
48 pixels físicos reservados às decorações antes da divisão. Em 32 casos, KWin
impôs limites adicionais; as dimensões solicitadas e efetivas constam dos JSONs.
O caso mais restrito usa 426×288 lógicos a 150%, aproximadamente 639×432 físicos.
Isso valida adaptação do conteúdo, mas não equivale a testar três monitores/VMs
reais com aquelas resoluções ou todas as decorações dos temas globais.

A primeira matriz registrou um SIGSEGV ao encerrar uma captura. Foi acrescentada
a retirada do filtro Python de tradução em `aboutToQuit`, antes da destruição dos
objetos Qt. Depois disso, o cenário passou em dez repetições e a matriz completa
foi repetida com 48/48 aprovações. O registro inicial permanece nas evidências;
não foi contado como aprovação.

Na matriz final, PSS ficou entre **51,7 e 57,8 MiB** e RSS entre **151,0 e
160,0 MiB**. São amostras de capturas locais, não medições de pico de transação
ou prova de estabilidade em computador limitado a 2 GB. Esse ensaio permanece
pendente, assim como a avaliação das decorações completas dos temas no ambiente
final. A ilustração original foi mantida sem gerar derivados maiores.

## Evidências e limites de escopo

As capturas e logs ficam em `dist/previa-acabamento/`, ignorado pelo Git:

- `claro/principal.png`, `escuro/principal.png`, `claro/agora-nao.png`.
- `matriz/`: capturas das janelas principal, técnica, confirmação, Agora não e
  programas após rolagem quando necessária.
- `matriz.json`, `matriz-resumo.json`, `matriz-primeira-execucao.json`.
- `encerramento.json`, `testes.log`, `testes-traducao.log`, `arquivos-antes.json`.

Para repetir uma captura:

```bash
QT_QPA_PLATFORM=wayland /usr/bin/python3 tools/preview-classic.py --long-list \
  --scheme /usr/share/color-schemes/BlurGlassyDark.colors \
  --capture-dir dist/previa-acabamento/repeticao
```

Para repetir a suíte:

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

Na implementação instalada, só a inicialização da tradução mudou, por meio da
nova função de localização. A janela principal do aplicativo ainda não foi
substituída pela prévia. `gui.py`, catálogo, PackageKit, PolicyKit, planejamento
de instalações, persistência, histórico, notificações, publicação, workflows e
configurações de produção permaneceram sem alterações nesta etapa. Não foram
criadas chaves nem executadas operações remotas.
