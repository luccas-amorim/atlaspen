---
titulo: Autoria e créditos
genero: créditos
data: '2026-09-24'
assinatura: Equipe AtlasPen
resumo: As mãos que constroem o AtlasPen.
---

## Quem somos

O AtlasPen é mantido pela **Equipe AtlasPen**, um grupo de pesquisa formado por
três pessoas: Luccas de Amorim Rêgo Cavicchioli, Maíra Rocha Machado e Luisa
Moraes Abreu Ferreira. O projeto não tem vínculo institucional formal e é
sustentado pelo trabalho voluntário de quem o integra.

Nasceu em junho de 2026, com o nome de trabalho *algo-pen*, como uma base com
cobertura completa dos tipos penais brasileiros, em código e dados abertos e em
planilha: o primeiro registro do repositório público é de 22 de junho de 2026.

## Quem faz o quê

Este projeto é uma confluência de direito penal e tecnologia. Cada campo do
catálogo é ao mesmo tempo uma linha num arquivo de dados e uma afirmação
jurídica (se o tipo é hediondo, se pressupõe violência, que ação penal cabe), e
as duas coisas precisam estar certas ao mesmo tempo.

**Luccas de Amorim Rêgo Cavicchioli** concebeu a versão de lançamento do projeto
e foi responsável pela sua construção: arquitetura, código, modelo de dados,
robôs de conferência e documentação. Escreveu os primeiros critérios de
classificação de cada campo, mantém o catálogo dia a dia e participa da pesquisa
acadêmica que orienta o desenvolvimento do sistema.

**Maíra Rocha Machado** (FGV Direito SP) coordenou, em 2008, a pesquisa que
originou o SISPENAS, antecedente intelectual do AtlasPen, e integra o grupo
desde junho de 2026. Participou das decisões de método e dos critérios de
classificação, idealizou a linha do tempo do
[Acervo histórico](../acervo/) e coordena a pesquisa acadêmica que expande o
projeto. Dela vem também a pergunta que o AtlasPen herdou: quantos tipos penais
existem, e qual é o alcance de uma alteração legislativa sobre o sistema penal?

**Luisa Moraes Abreu Ferreira** integra o grupo desde agosto de 2026. Trouxe ao
projeto documentos de pesquisa de sua autoria que orientaram decisões centrais
de modelo e de método, especialmente quanto aos crimes contra a dignidade
sexual, e orienta a pesquisa acadêmica que dá continuidade ao sistema.

Quem contribuir com o projeto — código, conferência de um diploma, revisão de
critérios, correção de erros — passa a constar aqui, com o que fez e desde
quando. O caminho é o [repositório](https://github.com/luccas-amorim/atlaspen).

## O antecedente: o SISPENAS (2008)

O SISPENAS (Sistema de Consulta sobre Crimes, Penas e Alternativas à Prisão) foi
o resultado de uma pesquisa coordenada por **Maíra Rocha Machado** e **Marta
Rodriguez de Assis Machado**, então na Direito GV, com **Fabio Andrade**,
**Priscilla Soares de Oliveira** e **Yuri Luz** na equipe, em resposta a um
edital da Secretaria de Assuntos Legislativos do Ministério da Justiça. Reunia
1.529 tipos penais e cruzava cada crime com as alternativas à prisão cabíveis,
nos dois sentidos, com simulação de alteração legislativa.

O AtlasPen recomeça do zero em código e dados, mas herda do SISPENAS a pergunta
e a intuição central: cruzar tipos e atributos penais e medir o efeito de uma
mudança legislativa sobre o conjunto. Por isso a referência completa da pesquisa
de 2008 acompanha toda citação do AtlasPen, e a
[íntegra do artigo](../artigos/machado-machado-2008-sispenas-rev-juridica-90.pdf)
está publicada junto com esta base. A história está contada em
[História do projeto](./).

## As fontes que os robôs leem

O texto que vale é o compilado do Planalto (`planalto.gov.br`). Desde outubro de
2026, os robôs de conferência leem também, só para perguntar, a
[API de Dados Abertos do Senado Federal](https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html)
e o portal [normas.leg.br](https://normas.leg.br), do Congresso Nacional, cujo
conteúdo está sob a licença CC BY 4.0. O Relator lê os precedentes do Supremo
Tribunal Federal no [Banco Nacional de Precedentes](https://pangeabnp.pdpj.jus.br) do
Conselho Nacional de Justiça. Nada que vem dessas fontes escreve no catálogo; o
critério está em [Os robôs](os-robos).

Parte do código de rede dos robôs foi adaptada do repositório
[ctresb/leis](https://github.com/ctresb/leis), de João Davi, sob a licença MIT. O
aviso da licença acompanha o código, em `scripts/robos/fontes/`.

## Como citar

A forma de citar o AtlasPen, e a de citar a pesquisa de 2008, estão em
[Dados abertos](dados-abertos#como-citar). O arquivo `CITATION.cff` do
repositório traz a mesma informação em formato que o GitHub e os gerenciadores
de referência leem.

O código está sob a licença Apache 2.0, e os dados e os textos, sob a CC BY 4.0.
As duas pedem o mesmo crédito: *AtlasPen, da Equipe AtlasPen*. A divisão está no
arquivo `NOTICE` do repositório.
