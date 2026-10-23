# Prévia da interface clássica

> Registro da rodada anterior. A ilustração e os ajustes atuais estão no
> [relatório de acabamento](acabamento-interface-classica.md). O banner TigerOS
> descrito abaixo foi retirado da prévia; as capturas anteriores são históricas.

Esta entrega é uma **prévia local separada**, para avaliar a composição antes
de incorporá-la ao aplicativo. `src/mainuan_recursos/gui.py`, os backends, a
publicação, o histórico e as configurações de segurança não foram alterados.
Não houve commit, push ou publicação. A produção permanece desativada.
O `.deb` e o arquivo de transferência da candidata anterior não foram refeitos;
esta prévia não faz parte daqueles artefatos.

## Abrir a prévia

Na raiz do checkout, dentro da sessão gráfica, **sem sudo**:

```bash
/usr/bin/python3 tools/preview-classic.py
```

O comando usa Python/PyQt6 já disponível no ambiente e respeita o estilo,
a paleta, os ícones e a escala Qt ativos. Não exige dependências novas.
Lê `message.txt` como texto simples, preservando quebras de linha; não interpreta
HTML. Os três programas são exemplos fictícios, gerados a partir de uma lista
única de nomes amigáveis e identificadores, sem consultas de disponibilidade.

Para avaliar as dimensões e uma paleta específica, sem alterar o tema global:

```bash
/usr/bin/python3 tools/preview-classic.py --size 640x480 \
  --scheme /usr/share/color-schemes/DreamCyanLightColor.colors

QT_SCALE_FACTOR=1.5 /usr/bin/python3 tools/preview-classic.py --size 640x480 \
  --scheme /usr/share/color-schemes/DreamCyanDarkColor.colors

/usr/bin/python3 tools/preview-classic.py --size 640x480 \
  --scheme /usr/share/color-schemes/BlurGlassy.colors

QT_SCALE_FACTOR=1.5 /usr/bin/python3 tools/preview-classic.py --size 426x288 \
  --scheme /usr/share/color-schemes/BlurGlassyDark.colors
```

Os nomes `.colors` acima existem neste computador; em outro ambiente, use o
caminho do esquema instalado. `--scheme` cria uma configuração temporária só
para o processo e usa o estilo Breeze. Sem essa opção, o estilo ativo é preservado.

Qt usa pixels **lógicos**. 640×480 lógicos a 150% exige 960×720 físicos, além
das decorações. O último exemplo usa 426×288 lógicos, cerca de 639×432 físicos,
reservando espaço para a janela em uma tela física de 640×480. Isso exercita a
composição reduzida neste desktop; não muda a resolução do monitor ou substitui
um ensaio numa tela/VM com essa resolução real.

## Composição e interações

- Banner original inteiro à esquerda, redimensionado proporcionalmente por Qt.
- Mensagem administrativa em destaque à direita, seguida dos nomes dos programas.
- Botões de tamanhos iguais, alinhados à direita: **Conhecer novidades** como
  botão padrão, com ícone e negrito; **Instalar novidades** secundário;
  **Agora não** discreto. O destaque usa o estilo Qt, sem cores fixadas.
- Menu discreto no canto superior direito: verificação, histórico e detalhes.
- Sem cartões, tabelas, painel lateral permanente ou informações técnicas na
  apresentação. Mensagens extensas têm rolagem; os botões ficam acessíveis.
- Em alturas reduzidas, as margens e o espaçamento diminuem e a mensagem passa
  a usar o tamanho de fonte normal do tema, mantendo o negrito.

O botão Conhecer abre somente a página oficial fixa
`https://github.com/mainuan/atualizadorderecursos/releases`, após o clique.
Os outros comandos apenas abrem diálogos de demonstração. Não há PackageKit,
PolicyKit, acesso ao catálogo ou persistência de histórico/adiamento nesta prévia.
Instalar apresenta uma confirmação fictícia com cancelamento; Agora não explica
o comportamento de 24 horas, sem gravar qualquer mudança. O menu técnico mostra
pacotes fictícios em versão 1.0 e informa que instalação/dependências não foram
consultadas. A prévia não declara nenhum recurso realmente instalado.

Na eventual incorporação, a apresentação deverá usar a mensagem e os nomes do
**catálogo já autenticado** (`Release.summary` e `Feature.title`), preservando os
fluxos atuais de confirmação, consulta, dependências, conclusão e estados. Não
introduzir leitura direta de `message.txt` remoto no cliente nem substituir os
controles existentes pelo comportamento fictício desta ferramenta.

## Ilustração e condições de reutilização

O [banner consultado no TigerOS](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/4bf16c13d3ae4098196e1a928e7a192b3967e16b/banner.png)
é idêntico ao blob do histórico local: PNG 398×320, 109.636 bytes, cerca de 107 KiB.
Preserva o pinguim olhando para o notebook. O tamanho é adequado para esta janela;
em tela pequena há redução proporcional. Não são aplicados efeitos, recortes,
alteração de cores ou recompressão; o fundo colorido original também permanece
em temas escuros. A baixa resolução original limita a nitidez em ampliações.

O [LICENSE da origem](https://github.com/Tiger-OperatingSystem/feature-update-manager/blob/main/LICENSE)
declara GPLv3 e é idêntico ao deste checkout. Não foi localizada licença separada
ou identificação do autor original da arte nos arquivos consultados. O histórico
de uploads não comprova autoria. A evidência disponível é a licença geral do
projeto: preservar licença e procedência e confirmar a origem com os mantenedores
antes da incorporação definitiva. Não se atribuiu autoria por suposição.

O arquivo e seus hashes estão documentados em
[preview-classic-assets/README.md](../tools/preview-classic-assets/README.md).

## Verificações executadas

No Mainuan físico, KDE/Wayland e Qt Breeze:

| Verificação | Resultado |
| --- | --- |
| 12 paletas Dream (seis cores, claro/escuro) e duas BlurGlassy, a 100% e 150% | 28 verificações aprovadas |
| Composição 800×480, BlurGlassy claro/escuro | 2 verificações aprovadas |
| Composição 426×288 a 150%, claro/escuro | 2 verificações aprovadas |
| Mensagem longa, com marcação exibida literalmente | 1 verificação aprovada |
| Abertura adicional sem impor esquema, no tema ativo | Aprovada |
| Suíte existente, sem alterações nos testes | 133 testes aprovados em 14,504 s |
| Inventário antes/depois de aplicação, configurações, publicação, testes e empacotamento | 87 arquivos existentes sem mudança de conteúdo |

As 33 verificações da matriz conferem: plataforma Wayland, correspondência da
paleta, três programas, texto simples, botões inteiramente dentro da janela,
mesmo tamanho e alinhamento, imagem contida e ausência de rolagem horizontal.
Depois da rolagem, o último programa permanece acessível. Foram capturadas a
janela principal, a consulta técnica e a confirmação, sem confirmar instalações.
As capturas são de widgets Qt; não incluem a decoração do compositor.

Na primeira execução, o roteiro de captura exigia tamanho idêntico ao solicitado.
Em 15 casos, o compositor limitou a altura de 480 para 457 pixels lógicos a 150%.
Os controles já cabiam. O verificador foi corrigido para registrar essa restrição
e exigir que a janela não cresça além do pedido e que as ações/conteúdos continuem
acessíveis. A matriz completa foi então repetida: 33/33 aprovadas. Esse ajuste
afeta apenas a ferramenta de prévia.

Na matriz final, PSS entre **43,5 e 48,2 MiB**, RSS entre **144,4 e 150,0 MiB**.
São amostras locais da janela aberta, sem carga real de consultas. Não representam
pico de instalação, estabilidade prolongada ou teste com limite de 2 GB.

Para repetir uma captura verificável:

```bash
QT_QPA_PLATFORM=wayland /usr/bin/python3 tools/preview-classic.py --size 640x480 \
  --scheme /usr/share/color-schemes/BlurGlassy.colors \
  --capture-dir dist/previa-classica/repeticao
```

Resultados, logs e imagens ficam em `dist/previa-classica/` (ignorado pelo Git):

- `classica-claro/principal.png`, `classica-escuro/principal.png`.
- `tela-fisica-640-claro/`, `tela-fisica-640-escuro/`.
- `mensagem-longa/`, incluindo os programas após rolagem.
- `matriz.json`, `matriz-primeira-execucao.json`, `testes-existentes.log`.
- `arquivos-antes.json`, inventário para conferir a preservação da implementação.

Continuam pendentes: avaliação visual do responsável, procedência específica da
arte, aplicação do tema global completo/decorações Dream e Blur-Glassy, teste
com resolução física reduzida e ensaio prolongado em VM limitada a 2 GB.
Não foi criada VM nem houve instalação no sistema. Nenhuma configuração de
produção foi habilitada.
