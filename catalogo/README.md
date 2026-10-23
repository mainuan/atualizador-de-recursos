# Catálogo oficial de novidades do Mainuan

Endereço reservado:
https://raw.githubusercontent.com/mainuan/atualizadorderecursos/main/catalogo/novidades.json

**Produção desativada.** `novidades.json` é a estrutura inicial vazia, sem
assinatura; não representa lançamento publicado. A configuração do aplicativo
continua com `keys: {}` e `publication.toml` permanece desabilitado, sem chaves.

A rotina de publicação usa apenas `packages.txt` e `message.txt` na raiz.
Depois da configuração inicial autorizada, o workflow gera automaticamente:

- `novidades.json` e `novidades.json.sig`: catálogo autenticado do aplicativo;
- `publicacao.json` e `publicacao.json.sig`: registro da seleção aprovada e dos
  pisos de versões, consumido pelo publicador;
- `apt/` na raiz: repositório APT assinado com os bytes congelados dos `.deb`.

Não editar esses arquivos gerados manualmente, apagar o registro nem voltar sua
sequência. Matérias inicialmente usam somente `https://github.com/mainuan/`;
sem artigo específico, a automação utiliza a página oficial da release.

Veja [publicação e configuração inicial](../docs/publicacao.md) e
[relatório de testes](../docs/publicacao-simples-relatorio.md). Chaves privadas e
chaves de teste não pertencem a este diretório. Nenhuma publicação foi ativada.
