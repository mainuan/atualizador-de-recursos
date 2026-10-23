# Finalização local da versão 0.2.1 — 23/10/2026

A candidata 0.2.1~rc1 foi aprovada em VM pelo responsável pelo Mainuan. Esta
finalização altera somente a ordem definitiva dos botões, identifica o aviso
nativo, atualiza a versão e verifica o empacotamento. Não publica no GitHub,
não faz push e não ativa produção nem infraestrutura APT adicional.

## Interface e segurança

Ordem vertical definitiva: **Instalar novidades**, **Conhecer novidades**,
**Agora não**. Largura, altura, espaçamento, alinhamento, composição clássica e
ilustração são preservados. Somente Instalar é padrão/negrito; Agora não mantém
borda e estilo convencional. A navegação por Tab segue a nova ordem.

A apresentação principal não contém avisos genéricos próprios sobre assinatura,
SHA-256 ou pacote não confiável. Esses detalhes continuam disponíveis no menu
de informações técnicas. Alertas de erros reais não são suprimidos.

O aviso da instalação local vem da ação nativa
`org.freedesktop.packagekit.package-install-untrusted`. Na política instalada em
`/usr/share/polkit-1/actions/org.freedesktop.packagekit.policy`, sua mensagem pt-BR
é “Autenticação é necessária para instalar softwares não confiáveis”.
O PackageKit seleciona essa ação para InstallFiles sem assinatura de repositório
reconhecida; quem apresenta a autorização é o agente PolicyKit da sessão.
[Código PackageKit](https://github.com/PackageKit/PackageKit/blob/v1.3.4/src/pk-transaction.c#L2626-L2632),
[política oficial](https://github.com/PackageKit/PackageKit/blob/v1.3.4/policy/org.freedesktop.packagekit.policy.in#L44-L60).

Essa proteção foi mantida: não há interceptação do diálogo, alteração de política
ou permissão global. A explicação no menu não é outra janela de instalação.
Reconhecer futuramente a origem por APT assinado continua fora desta entrega.

Não foram alterados consulta dos dois arquivos editoriais, download após o clique,
hash/origem aprovados, simulações/revalidações, PackageKit/PolicyKit, progresso,
conclusão verificada, histórico, adiamento, proteção de sessão Live ou Wayland.

## Auditoria AMD64/x86-64-v1

O pacote declara **Architecture: all**. Não compila C/C++, Rust, extensões Python
ou qualquer outro executável nativo. O launcher é um script Python. Qt/PyQt6,
python-apt, cryptography e PackageKit são dependências fornecidas pela distribuição,
sem cópia de suas bibliotecas para o pacote.

Foram revisados build.sh, build-package.sh, tools/stage-package.sh, debian/rules,
debian/control, ferramentas auxiliares e os workflows do GitHub Actions. Não há
invocação de compilador nativo, -march=native, requisitos v2/v3/v4, AVX/AVX2/FMA,
PyInstaller/Nuitka ou wheels incorporados no fluxo. dh_auto_build está explicitamente
vazio; os demais passos copiam scripts/dados e constroem arquivos Debian/índices.

O ambiente da construção não define CFLAGS/CXXFLAGS/CPPFLAGS/RUSTFLAGS/GOAMD64
ou substituições CC/CXX. As flags padrão informadas por dpkg-buildflags foram
inspecionadas, sem -march ou AVX; **nenhuma flag de compilação nativa é efetivamente
utilizada pelo projeto**, porque não existe compilação nativa. Não foram adicionadas
flags decorativas que alegassem mudar a compatibilidade de Python ou de bibliotecas
externas. Caso existisse C/C++, o alvo AMD64 v1 apropriado seria
`-march=x86-64 -mtune=generic`, sem opções que elevassem esse alvo.
[Documentação GCC](https://gcc.gnu.org/onlinedocs/gcc/x86-Options.html).

O construtor local e o workflow verificam a versão exata, Architecture: all e a
ausência de ELF, arquivos nativos e bibliotecas incorporadas com
`tools/audit_python_package.py`. O workflow seleciona exclusivamente o nome de
pacote correspondente ao changelog, evitando anexar pacotes antigos por wildcard.
O verificador só inspeciona o arquivo; não o instala nem executa seu conteúdo.

O aplicativo próprio, sem código de máquina incorporado, não introduz requisito
de instruções acima de v1. A compatibilidade completa depende também de Python,
Qt/PyQt6 e demais bibliotecas **baseline** presentes na imagem Mainuan. `amd64`
continua sendo o nome Debian correto; não foi criada uma arquitetura amd64v1 nem
adicionada dependência amd64v3. O Ubuntu fornece uma variante amd64v3 distinta,
que não deve substituir a base destinada aos computadores antigos.
[Arquiteturas Ubuntu](https://documentation.ubuntu.com/project/how-ubuntu-is-made/concepts/supported-architectures/).

Foi feita leitura adicional de notas ELF das dependências locais (não incorporadas):
Python e libc declaram x86-64-baseline. Nas bibliotecas Qt/PyQt examinadas não foi
encontrada declaração de ISA obrigatória v2/v3/v4. Algumas não possuem declaração
de ISA mínima. **Ausência de nota não comprova ausência de instruções avançadas**;
notas GNU, arquitetura nominal e inspeção estática isolada não certificam todos
os caminhos de execução ou dependências transitivas.

Não há QEMU user/system ou ambiente identificado de CPU v1 disponível nesta sessão.
Não foi instalado emulador nem alterada a CPU da VM do usuário. Portanto, o resultado
é **validação estática do pacote próprio**, não certificação da distribuição inteira.
O teste do conjunto Mainuan/Python/Qt em processador v1 real permanece pendente.

## Construção e evidências

```bash
QT_QPA_PLATFORM=offscreen PYTHONPATH=src /usr/bin/python3 -m unittest discover -s tests -v
bash build-package.sh
python3 tools/audit_python_package.py dist/mainuan-atualizador-recursos_0.2.1_all.deb --expected-version 0.2.1
lintian dist/mainuan-atualizador-recursos_0.2.1_all.deb
```

O pacote final e checksum ficam em `dist/final-0.2.1/`. Os relatórios de testes,
auditoria de payload/control, notas ELF das dependências e origem do aviso também
ficam nesse diretório. Não se reutiliza a candidata 0.2.1~rc1: a versão final é
construída em preparação nova e o conteúdo é comparado com os fontes atuais.
