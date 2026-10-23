# Testes e homologação

## Fluxo sem alterar o sistema

```bash
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo
```

Use **Conhecer novidades**, **Instalar novidades**, revise a confirmação e aceite.
A autorização é simulada e identificada como demonstração. Ao concluir, a tabela
mostra os recursos recebidos, o botão de instalação fica desabilitado e o estado
é atualizado somente em memória. Reiniciar o demo restaura os dados fictícios.
A matéria de exemplo usa `mainuan.example`, um endereço reservado sem conteúdo
real. O navegador é a única integração externa habilitada no demo.

Use `--scenario` para exercitar `novo`, `visualizado`, `adiado`, `instalado`,
`parcial`, `indisponivel`, `incompativel`, `erro` e `cancelado`. Para conferir a
supressão automática, combine com `--check`: primeira consulta após 60 segundos,
depois a cada hora. O histórico continua acessível na execução manual.

### Exercitar assinatura com catálogo local

```bash
/usr/bin/python3 tools/dev-catalog.py /tmp/mainuan-catalogo-teste
/usr/bin/python3 tools/catalog.py verify /tmp/mainuan-catalogo-teste/catalog.json \
  --config /tmp/mainuan-catalogo-teste/config.json
PYTHONPATH=src /usr/bin/python3 -m mainuan_recursos --demo \
  --test-catalog /tmp/mainuan-catalogo-teste/catalog.json \
  --test-config /tmp/mainuan-catalogo-teste/config.json
```

Nenhuma chave ou configuração de produção é acessada/modificada nesse modo. A
ferramenta cria datas atuais, assinatura válida, chave privada descartável 0600
e configuração de teste. A interface usa pacotes simulados mesmo quando os nomes
coincidem com pacotes reais. Altere um byte do catálogo e repita `verify`: deve
falhar. Para voltar a assinar, use `tools/catalog.py sign` com os arquivos de teste.
Não copie essas chaves para `data/` ou `/etc/mainuan/`.

## Suíte automatizada

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
```

Cobre assinatura/tampering/chave desconhecida, tipos e limites, duplicações,
URLs e travessia de caminhos, expiração, replay, cache, versões Debian,
origens/dependências, pacotes retidos e configuração incompleta, alterações após
confirmação, cancelamento/erro/queda do daemon, progresso e conclusão verificada.
Inclui interação real com Widgets no fluxo demo e adiamento com relógio controlado.
Nenhuma transação real de instalação é criada pelos testes.

O GitHub Actions repete os testes em Ubuntu 26.04, valida desktop files e gera
`.deb` com debhelper. A versão local simples usa `bash build-package.sh` sem root.
O pacote pode ser inspecionado ou extraído em diretório temporário com
`dpkg-deb --info`, `--contents` e `--extract`, sem instalá-lo.

## Homologação adicional em VM Mainuan

Estas verificações exigem sessão gráfica e, na etapa de instalação, modificam
apenas a VM descartável. Não são substituídas pelos testes offscreen:

- Plasma 6/Wayland com temas claro/escuro, Dream e Blur-Glassy; escalas 100/150/200%,
  navegação por teclado, leitor de tela e largura reduzida.
- Instalação real do `.deb`, menu e autostart, início de sessão fluido, detecção
  Live, duas execuções simultâneas e ativação manual da janela oculta.
- Catálogo e assinatura publicados com chave de homologação provisionada **na VM**;
  ausência de rede, validade vencida, HTTP ou redirecionamento para outra conta.
- Repositório APT de teste autenticado, programa novo e programa instalado em
  versão antiga, pacote já recebido, candidato ausente, origem não confiável,
  dependência nova e pacote retido. Não habilite confiança insegura em produção.
- Clique explícito, operação completa na confirmação, autorização PolicyKit
  aceita/negada/cancelada, concorrência com Discover e erros de download/dpkg.
- Verifique a versão e configuração efetivas no dpkg após instalação; reinicie
  o aplicativo e confirme que não oferece reinstalação. Atualize um recurso pelo
  atualizador tradicional e confira **Já recebido** no canal de novidades.
- Durante a confirmação, altere o candidato ou dependências pela VM; a nova
  operação deve exigir preparação e confirmação novamente.

Os estados reais ficam em `$XDG_STATE_HOME/mainuan-recursos/state.json` (padrão
`~/.local/state/mainuan-recursos/`). Cache e lock estão no mesmo diretório.
Preserve esse arquivo ao investigar falhas; apagar o estado reinicia a proteção
local de sequência e o histórico. Para desenvolvimento, prefira sempre o demo.

Não há rollback automático. Entre simulação e commit, outro processo pode alterar
o universo de pacotes; revalidação e flags conservadoras reduzem a janela, sem
criar uma transação atômica entre os aplicativos.

## Resultado da auditoria posterior

A auditoria ampliou a suíte para 92 testes e acrescentou ensaios reais de
instância única, capturas em Wayland e ciclo dpkg em raiz descartável. Veja
[homologacao.md](homologacao.md) para resultados, métricas, reprodução e a
separação explícita das pendências de VM. O diálogo de confirmação agora mostra
a operação completa com rolagem, sem precisar expandir detalhes.


A etapa de [integrações reais e preparação da VM](vm-final.md) ampliou a suíte
para 101 testes e corrigiu falsos positivos na identificação Live. Esse relatório
separa probes de leitura/simulação de instalações e autenticação ainda não homologadas.
