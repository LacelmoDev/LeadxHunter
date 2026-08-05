# Lead Hunter 🎯

Ferramenta pessoal para encontrar negócios locais **sem site**, prontos para
receber uma proposta de website, hospedagem ou automação de WhatsApp.

100% gratuita: usa OpenStreetMap (Overpass API) + Nominatim para geocodificação.
Não precisa de nenhuma chave de API.

## Como rodar

1. Instale o Python 3.10+ (se ainda não tiver).
2. Abra um terminal na pasta `lead_hunter` e instale as dependências:

   ```bash
   pip install -r requirements.txt
   ```

3. Rode o app:

   ```bash
   streamlit run app.py
   ```

4. Vai abrir automaticamente no navegador (geralmente `http://localhost:8501`).

## Colocar uma senha (recomendado antes de hospedar online)

O app já vem com uma tela de login simples. Pra ativar:

1. Dentro da pasta `.streamlit`, copie `secrets.toml.example` para um novo
   arquivo chamado `secrets.toml` (mesmo lugar, só tirar o `.example` do nome).
2. Abra o `secrets.toml` e troque `"troque-esta-senha"` pela senha que você
   quiser usar.
3. Rode o app normalmente — agora ele vai pedir a senha antes de mostrar
   qualquer coisa.

O arquivo `secrets.toml` real **nunca deve ser enviado pro GitHub** (o
`.gitignore` já está configurado pra ignorá-lo automaticamente).

## Hospedar de graça (pra usar do celular, sem precisar do PC ligado)

Usando o **Streamlit Community Cloud** (gratuito):

1. Crie uma conta gratuita em https://github.com (se ainda não tiver).
2. Crie um repositório novo (pode ser privado) e suba todos os arquivos
   desta pasta **exceto** o `.streamlit/secrets.toml` (o `.gitignore` já
   cuida disso se você usar `git add` normalmente).
3. Crie uma conta gratuita em https://share.streamlit.io usando o mesmo
   login do GitHub.
4. Clique em **"New app"**, escolha o repositório que você criou, e selecione
   `app.py` como arquivo principal.
5. Antes de publicar, vá em **"Advanced settings" → "Secrets"** e cole:

   ```toml
   APP_PASSWORD = "sua-senha-aqui"
   ```

6. Clique em **Deploy**. Em alguns minutos você recebe um link público
   (tipo `https://seu-app.streamlit.app`) que abre em qualquer navegador,
   inclusive do celular — só vai pedir a senha antes de liberar o acesso.

**Importante:** como o link fica público na internet, qualquer pessoa que
tiver o link E a senha consegue acessar. Não compartilhe a senha com
ninguém fora da tua operação.

## Como usar

1. Na barra lateral, escolha a **categoria** do negócio (cabeleireiro, restaurante,
   oficina, etc.) e digite a **cidade/bairro** (ex: `Talatona, Luanda`).
2. Clique em **Buscar leads**.
3. A tabela mostra os negócios encontrados, ordenados por um **score de 0 a 100**
   que indica o quão "promissor" é o lead (tem telefone/WhatsApp, endereço completo,
   horário definido, e se realmente não tem site).
4. Use o filtro de **score mínimo** para focar só nos melhores.
5. Pra abordar um lead, use a seção **"Abordar um lead"**: escolha o nome, ajuste
   a mensagem se quiser, e clique pra abrir o WhatsApp já preenchido.
6. Baixe a lista em **Excel** ou **CSV** pra usar na tua rotina diária de prospecção.

## Adicionar novas categorias

No arquivo `overpass.py`, edite o dicionário `CATEGORIAS`. Cada entrada é o nome
que aparece no app, ligado a uma lista de tags do OpenStreetMap. Por exemplo:

```python
"Pet shop": [("shop", "pet")],
```

Para descobrir a tag certa de uma categoria nova, pesquise em
https://wiki.openstreetmap.org/wiki/Map_Features

## Limitações a saber

- A qualidade dos dados depende do que já foi cadastrado no OpenStreetMap —
  em algumas zonas pode ter poucos negócios mapeados. Se um resultado vier vazio,
  tente uma área maior (ex: a cidade inteira em vez do bairro).
- O campo "site" só é confiável quando o próprio negócio (ou alguém) cadastrou
  a informação no mapa — ou seja, "sem site" aqui significa "sem site
  cadastrado no OSM", que na prática é um ótimo proxy, mas vale confirmar com
  uma busca rápida no Google antes de fechar a abordagem.
- Se a Overpass API estiver lenta/instável (é um servidor comunitário gratuito),
  espere alguns segundos e tente de novo.

## Próximos passos possíveis

- Adicionar um campo de "status" (contatado / respondeu / fechado) direto na
  tabela, salvando localmente, pra virar um CRM simples do dia a dia.
- Puxar avaliações/fotos do Google Places (tem cota gratuita mensal) pra
  enriquecer o score quando o Overpass tiver poucos dados.
