"""
overpass.py
Responsável por:
 1. Geocodificar o nome de uma cidade/bairro (via Nominatim, gratuito)
 2. Buscar negócios de uma categoria dentro dessa área (via Overpass API, gratuito)
 3. Filtrar e organizar os que NÃO têm site cadastrado
 4. Calcular um "score de lead promissor" com os dados disponíveis
"""

import time
import requests
import pandas as pd

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Mapa de categorias em português -> tags do OpenStreetMap.
# Cada categoria pode corresponder a mais de uma tag (ex: shop=hairdresser cobre
# tanto "cabeleireiro" quanto "barbearia" em alguns cadastros).
CATEGORIAS = {
    "Cabeleireiro / Barbearia": [("shop", "hairdresser"), ("shop", "beauty")],
    "Oficina mecânica": [("shop", "car_repair")],
    "Restaurante / Lanchonete": [("amenity", "restaurant"), ("amenity", "fast_food")],
    "Padaria / Pastelaria": [("shop", "bakery"), ("shop", "pastry")],
    "Mercearia / Minimercado": [("shop", "convenience"), ("shop", "supermarket")],
    "Farmácia": [("amenity", "pharmacy")],
    "Loja de roupas": [("shop", "clothes")],
    "Loja de eletrônicos": [("shop", "electronics")],
    "Clínica / Consultório": [("amenity", "clinic"), ("amenity", "doctors")],
    "Escola / Centro de formação": [("amenity", "school"), ("amenity", "college")],
    "Hotel / Pensão": [("tourism", "hotel"), ("tourism", "guest_house")],
    "Loja de material de construção": [("shop", "hardware"), ("shop", "doityourself")],
    "Academia / Ginásio": [("leisure", "fitness_centre")],
    "Papelaria": [("shop", "stationery")],
}

# Para cada categoria: (o que a pessoa estava procurando, a informação que não encontrou)
# Usado pra montar a cena de busca frustrada na mensagem — a dor concreta de
# um cliente que procurou e não achou, em vez de uma promessa genérica.
CENA_BUSCA_POR_CATEGORIA = {
    "Cabeleireiro / Barbearia": ("um cabeleireiro/barbearia aqui perto", "os horários disponíveis"),
    "Oficina mecânica": ("uma oficina de confiança", "os serviços e um contacto direto"),
    "Restaurante / Lanchonete": ("onde comer aqui perto", "o cardápio e os preços"),
    "Padaria / Pastelaria": ("uma padaria aqui perto", "o que vocês vendem"),
    "Mercearia / Minimercado": ("um minimercado aqui perto", "se tinham o que eu precisava"),
    "Farmácia": ("uma farmácia aberta agora", "o horário de funcionamento"),
    "Loja de roupas": ("uma loja de roupas", "as peças que vocês têm"),
    "Loja de eletrônicos": ("uma loja de eletrónicos", "os preços dos produtos"),
    "Clínica / Consultório": ("uma clínica aqui perto", "como marcar uma consulta"),
    "Escola / Centro de formação": ("um curso", "as turmas e como me inscrever"),
    "Hotel / Pensão": ("hospedagem aqui perto", "fotos e preços"),
    "Loja de material de construção": ("uma loja de material de construção", "se tinham o que eu precisava"),
    "Academia / Ginásio": ("uma academia aqui perto", "os planos e horários"),
    "Papelaria": ("uma papelaria aqui perto", "se tinham um material específico"),
}
CENA_PADRAO = ("um negócio como o vosso aqui perto", "informação básica")


def limpar_telefone(numero: str, ddi_padrao: str = "244") -> str:
    """
    Limpa um número de telefone para o formato aceito pelo link wa.me
    (apenas dígitos, com código do país na frente, sem + nem espaços).
    Assume Angola (244) como padrão quando o número não tem código de país.
    """
    if not numero:
        return ""
    digitos = "".join(c for c in numero if c.isdigit())
    if not digitos:
        return ""
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if digitos.startswith(ddi_padrao):
        return digitos
    if digitos.startswith("0"):
        digitos = digitos[1:]
    return f"{ddi_padrao}{digitos}"


def gerar_mensagem_whatsapp(nome: str, categoria: str) -> str:
    """
    Gera uma mensagem curta de primeiro contacto que abre com a cena de uma
    busca frustrada (a dor real de um cliente perdido), e só depois oferece
    a solução — em vez de começar já vendendo o serviço.
    """
    procurava, nao_achou = CENA_BUSCA_POR_CATEGORIA.get(categoria, CENA_PADRAO)
    return (
        f"Olá! Andei à procura de {procurava} e cheguei até a {nome} — "
        f"só que quando fui ver {nao_achou} no Google/Instagram, não encontrei nada. "
        f"Isso deve fazer bastante gente desistir e ir pra outro lugar. "
        f"Eu ajudo negócios como o vosso a resolver isso com um site simples ou "
        f"uma automação de WhatsApp. Faz sentido conversarmos 5 minutos?"
    )


def montar_link_whatsapp(telefone_ou_whatsapp: str, nome: str, categoria: str) -> str:
    """Monta o link wa.me com a mensagem já preenchida, pronto pra um clique."""
    numero = limpar_telefone(telefone_ou_whatsapp)
    if not numero:
        return ""
    from urllib.parse import quote
    mensagem = gerar_mensagem_whatsapp(nome, categoria)
    return f"https://wa.me/{numero}?text={quote(mensagem)}"


def geocode_local(nome_local: str, timeout: int = 15):
    """Converte um nome de cidade/bairro em uma bounding box (south, west, north, east)."""
    params = {
        "q": nome_local,
        "format": "json",
        "limit": 1,
    }
    headers = {"User-Agent": "lead-hunter-app/1.0"}
    resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=timeout)
    resp.raise_for_status()
    dados = resp.json()
    if not dados:
        return None
    item = dados[0]
    # boundingbox vem como [south, north, west, east] em string
    bbox = item["boundingbox"]
    south, north, west, east = map(float, bbox)
    return {
        "display_name": item.get("display_name", nome_local),
        "bbox": (south, west, north, east),
        "lat": float(item["lat"]),
        "lon": float(item["lon"]),
    }


def montar_query_overpass(tags, bbox, raio_extra=0.0):
    """Monta a query Overpass QL para uma lista de tags dentro de uma bbox."""
    south, west, north, east = bbox
    south -= raio_extra
    west -= raio_extra
    north += raio_extra
    east += raio_extra

    partes = []
    for chave, valor in tags:
        partes.append(f'node["{chave}"="{valor}"]({south},{west},{north},{east});')
        partes.append(f'way["{chave}"="{valor}"]({south},{west},{north},{east});')

    query = f"""
    [out:json][timeout:60];
    (
      {''.join(partes)}
    );
    out center tags;
    """
    return query


def buscar_leads(categoria: str, nome_local: str, apenas_sem_site: bool = True, timeout: int = 60):
    """
    Função principal: retorna um DataFrame com os leads encontrados.
    Lança ValueError se o local não for encontrado.
    """
    if categoria not in CATEGORIAS:
        raise ValueError(f"Categoria desconhecida: {categoria}")

    local = geocode_local(nome_local)
    if local is None:
        raise ValueError(f"Não consegui localizar '{nome_local}'. Tente ser mais específico (ex: 'Talatona, Luanda').")

    tags = CATEGORIAS[categoria]
    query = montar_query_overpass(tags, local["bbox"])

    headers = {
        "User-Agent": "lead-hunter-app/1.0 (uso pessoal)",
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    resp = requests.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=timeout)
    if resp.status_code == 429:
        raise ValueError(
            "A Overpass API está sobrecarregada agora (erro 429 - muitas requisições). "
            "Espere um pouco (30s-1min) e tente novamente."
        )
    if resp.status_code == 504:
        raise ValueError(
            "A busca demorou demais e o servidor da Overpass cortou a conexão (erro 504). "
            "Tente uma área menor ou tente de novo em alguns segundos."
        )
    resp.raise_for_status()
    elementos = resp.json().get("elements", [])

    linhas = []
    vistos = set()
    for el in elementos:
        tags_el = el.get("tags", {})
        nome = tags_el.get("name")
        if not nome:
            continue
        if nome in vistos:
            continue
        vistos.add(nome)

        tem_site = bool(tags_el.get("website") or tags_el.get("contact:website"))
        if apenas_sem_site and tem_site:
            continue

        telefone = tags_el.get("phone") or tags_el.get("contact:phone") or ""
        whatsapp = tags_el.get("contact:whatsapp") or ""
        endereco_partes = [
            tags_el.get("addr:street", ""),
            tags_el.get("addr:housenumber", ""),
            tags_el.get("addr:suburb", "") or tags_el.get("addr:city", ""),
        ]
        endereco = " ".join(p for p in endereco_partes if p).strip()
        horario = tags_el.get("opening_hours", "")

        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")

        # --- Score de lead promissor (0 a 100) ---
        score = 0
        motivos = []
        if telefone or whatsapp:
            score += 40
            motivos.append("tem contacto")
        if endereco:
            score += 20
            motivos.append("endereço completo")
        if horario:
            score += 20
            motivos.append("horário definido")
        if not tem_site:
            score += 20
            motivos.append("sem site")

        contacto_principal = whatsapp or telefone
        mensagem_sugerida = gerar_mensagem_whatsapp(nome, categoria)
        link_whatsapp = montar_link_whatsapp(contacto_principal, nome, categoria)

        linhas.append({
            "Nome": nome,
            "Categoria": categoria,
            "Telefone": telefone,
            "WhatsApp": whatsapp,
            "Endereço": endereco,
            "Horário": horario,
            "Tem site?": "Sim" if tem_site else "Não",
            "Score": score,
            "Motivo do score": ", ".join(motivos),
            "Mensagem sugerida": mensagem_sugerida,
            "Abrir WhatsApp": link_whatsapp,
            "Latitude": lat,
            "Longitude": lon,
            "Link Google Maps": (
                f"https://www.google.com/maps?q={lat},{lon}" if lat and lon else ""
            ),
        })

    df = pd.DataFrame(linhas)
    if not df.empty:
        df = df.sort_values("Score", ascending=False).reset_index(drop=True)
    return df, local["display_name"]
