from django.db import models
from django.utils import timezone


class SiteMonitorado(models.Model):
    nome = models.CharField(max_length=150)
    url_base = models.URLField()
    ativo = models.BooleanField(default=True)
    observacao = models.TextField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site monitorado"
        verbose_name_plural = "Sites monitorados"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Categoria(models.Model):
    nome = models.CharField(max_length=150)
    categoria_pai = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="subcategorias"
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ["nome"]

    def __str__(self):
        if self.categoria_pai:
            return f"{self.categoria_pai} > {self.nome}"
        return self.nome


class Marca(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    observacao = models.TextField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class FabricanteImportador(models.Model):
    TIPO_CHOICES = [
        ("FABRICANTE", "Fabricante"),
        ("IMPORTADOR", "Importador"),
        ("DISTRIBUIDOR_OFICIAL", "Distribuidor oficial"),
        ("OUTRO", "Outro"),
    ]

    nome = models.CharField(max_length=200)
    tipo = models.CharField(
        max_length=30,
        choices=TIPO_CHOICES,
        default="FABRICANTE"
    )
    site_oficial = models.URLField(blank=True, null=True)
    pais_origem = models.CharField(max_length=100, blank=True, null=True)
    observacao = models.TextField(blank=True, null=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Fabricante / Importador"
        verbose_name_plural = "Fabricantes / Importadores"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class ProdutoReferencia(models.Model):
    FONTE_VALIDACAO_CHOICES = [
        ("SITE_FABRICANTE", "Site do fabricante"),
        ("SITE_IMPORTADOR", "Site do importador"),
        ("CATALOGO_OFICIAL", "Catálogo oficial"),
        ("MANUAL_EMBALAGEM", "Manual ou embalagem"),
        ("OUTRA", "Outra fonte"),
    ]

    STATUS_VALIDACAO_CHOICES = [
        ("PENDENTE", "Pendente"),
        ("VALIDADO", "Validado"),
        ("DIVERGENTE", "Divergente"),
        ("SEM_REFERENCIA", "Sem referência oficial"),
    ]

    nome_referencia = models.CharField(
        max_length=500,
        help_text="Nome oficial ou tratado do produto conforme fonte de referência."
    )

    marca = models.ForeignKey(
        Marca,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    fabricante_importador = models.ForeignKey(
        FabricanteImportador,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        help_text="Fabricante, importador ou distribuidor oficial responsável pelo produto."
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    codigo_fabricante = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_index=True,
        help_text="Código original informado pelo fabricante/importador."
    )

    ean = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
        help_text="Código de barras EAN/GTIN. Deve ser tratado como texto."
    )

    url_oficial = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
        help_text="URL da fonte oficial usada para validar o produto."
    )

    fonte_validacao = models.CharField(
        max_length=30,
        choices=FONTE_VALIDACAO_CHOICES,
        default="SITE_FABRICANTE"
    )

    status_validacao = models.CharField(
        max_length=30,
        choices=STATUS_VALIDACAO_CHOICES,
        default="PENDENTE"
    )

    observacao_validacao = models.TextField(blank=True, null=True)
    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto referência"
        verbose_name_plural = "Produtos referência"
        ordering = ["nome_referencia"]

    def __str__(self):
        return self.nome_referencia


class ProdutoColetado(models.Model):
    STATUS_VINCULO_CHOICES = [
        ("PENDENTE", "Pendente de validação"),
        ("VINCULADO", "Vinculado ao produto referência"),
        ("DIVERGENTE", "Divergente"),
        ("SEM_REFERENCIA", "Sem referência encontrada"),
    ]

    site = models.ForeignKey(SiteMonitorado, on_delete=models.CASCADE)

    produto_referencia = models.ForeignKey(
        ProdutoReferencia,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="produtos_coletados",
        help_text="Produto oficial/referência usado para comparar o mesmo item entre sites."
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    marca = models.ForeignKey(
        Marca,
        on_delete=models.SET_NULL,
        blank=True,
        null=True
    )

    nome_original = models.CharField(max_length=500)

    codigo_site = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Código interno do produto no site monitorado."
    )

    codigo_fabricante = models.CharField(
        max_length=150,
        blank=True,
        null=True,
        db_index=True,
        help_text="Código original do produto informado no site de venda."
    )

    ean = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        db_index=True,
        help_text="Código de barras EAN/GTIN informado no site de venda."
    )

    url = models.URLField(max_length=1000)

    status_vinculo = models.CharField(
        max_length=30,
        choices=STATUS_VINCULO_CHOICES,
        default="PENDENTE"
    )

    ativo = models.BooleanField(default=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Produto coletado"
        verbose_name_plural = "Produtos coletados"
        ordering = ["nome_original"]
        unique_together = ["site", "url"]

    def __str__(self):
        return self.nome_original


class ColetaProduto(models.Model):
    produto = models.ForeignKey(
        ProdutoColetado,
        on_delete=models.CASCADE,
        related_name="coletas"
    )

    estoque = models.IntegerField(null=True, blank=True)

    data_coleta = models.DateTimeField(auto_now_add=True)

    preco_atual = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    preco_antigo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True
    )

    preco_prazo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Preço total a prazo/cartão, quando informado no site.",
    )

    quantidade_parcelas = models.IntegerField(
        blank=True,
        null=True,
        help_text="Quantidade máxima de parcelas informada no site.",
    )

    valor_parcela = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Valor da parcela informada no site.",
    )

    desconto_percentual = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True
    )

    nota_media = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        blank=True,
        null=True
    )

    quantidade_avaliacoes = models.IntegerField(blank=True, null=True)

    ranking_geral = models.IntegerField(blank=True, null=True)
    ranking_categoria = models.IntegerField(blank=True, null=True)

    disponivel = models.BooleanField(default=True)
    texto_disponibilidade = models.CharField(max_length=200, blank=True, null=True)

    observacao = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "Coleta de produto"
        verbose_name_plural = "Coletas de produtos"
        ordering = ["-data_coleta"]

    def __str__(self):
        return f"{self.produto} - {self.data_coleta.strftime('%d/%m/%Y %H:%M')}"
    
class ExecucaoColeta(models.Model):
    STATUS_CHOICES = [
        ("EM_EXECUCAO", "Em execução"),
        ("SUCESSO", "Sucesso"),
        ("ERRO", "Erro"),
        ("SEM_DADOS", "Sem dados"),
    ]

    TIPO_COLETA_CHOICES = [
        ("MAIS_VENDIDOS", "Mais vendidos"),
        ("CATEGORIA", "Categoria"),
        ("BUSCA", "Busca"),
        ("OUTRA", "Outra"),
    ]

    site = models.ForeignKey(
        SiteMonitorado,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="execucoes_coleta",
    )

    tipo_coleta = models.CharField(
        max_length=30,
        choices=TIPO_COLETA_CHOICES,
        default="MAIS_VENDIDOS",
    )

    nome_fonte = models.CharField(
        max_length=200,
        default="Mais vendidos",
    )

    url_base = models.URLField(
        max_length=1000,
        blank=True,
        null=True,
    )

    data_inicio = models.DateTimeField(
        default=timezone.now,
    )

    data_fim = models.DateTimeField(
        blank=True,
        null=True,
    )

    limite_solicitado = models.IntegerField(
        blank=True,
        null=True,
    )

    max_paginas = models.IntegerField(
        blank=True,
        null=True,
    )

    paginas_processadas = models.IntegerField(
        default=0,
    )

    produtos_encontrados = models.IntegerField(
        default=0,
    )

    produtos_novos = models.IntegerField(
        default=0,
    )

    produtos_atualizados = models.IntegerField(
        default=0,
    )

    coletas_gravadas = models.IntegerField(
        default=0,
    )

    dry_run = models.BooleanField(
        default=False,
    )

    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default="EM_EXECUCAO",
    )

    mensagem_erro = models.TextField(
        blank=True,
        null=True,
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Execução de coleta"
        verbose_name_plural = "Execuções de coleta"
        ordering = ["-data_inicio"]

    def __str__(self):
        return f"{self.nome_fonte} - {self.get_status_display()} - {self.data_inicio.strftime('%d/%m/%Y %H:%M')}"

    @property
    def duracao_segundos(self):
        if not self.data_inicio or not self.data_fim:
            return None

        return round((self.data_fim - self.data_inicio).total_seconds(), 2)
    
class AlvoColeta(models.Model):
    class Coletor(models.TextChoices):
        LOJA_MECANICO = "loja_mecanico", "Loja do Mecânico"
        DUTRA_MAQUINAS = "dutra_maquinas", "Dutra Máquinas"
        FERRAMENTAS_KENNEDY = "ferramentas_kennedy", "Ferramentas Kennedy"

    class SituacaoUltimaExecucao(models.TextChoices):
        PENDENTE = "PENDENTE", "Pendente"
        SUCESSO = "SUCESSO", "Sucesso"
        ERRO = "ERRO", "Erro"

    nome = models.CharField(
        max_length=255,
        help_text="Nome interno para identificar esta coleta.",
    )

    coletor = models.CharField(
        max_length=50,
        choices=Coletor.choices,
        help_text="Qual coletor será usado para esta URL.",
    )

    servico_coleta = models.CharField(
        max_length=50,
        default="servico_01",
        db_index=True,
        help_text="Identificador do agente/serviço responsável por executar este alvo. Ex: servico_01.",
    )

    nome_fonte = models.CharField(
        max_length=255,
        help_text="Nome da fonte que aparecerá nos relatórios. Ex: Dutra - Alicates.",
    )

    url = models.URLField(
        max_length=1000,
        help_text="URL da categoria, busca, campanha ou página que será coletada.",
    )

    site_monitorado = models.ForeignKey(
        SiteMonitorado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alvos_coleta",
    )

    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alvos_coleta",
    )

    ativo = models.BooleanField(default=True)

    limite = models.PositiveIntegerField(
        default=500,
        help_text="Quantidade máxima de produtos a coletar.",
    )

    max_paginas = models.PositiveIntegerField(
        default=10,
        help_text="Quantidade máxima de páginas a percorrer.",
    )

    ordem = models.PositiveIntegerField(
        default=0,
        help_text="Ordem de execução. Menor número roda primeiro.",
    )

    ultima_execucao = models.DateTimeField(null=True, blank=True)

    ultima_situacao = models.CharField(
        max_length=20,
        choices=SituacaoUltimaExecucao.choices,
        default=SituacaoUltimaExecucao.PENDENTE,
    )

    ultima_mensagem = models.TextField(blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["servico_coleta", "ordem", "id"]
        verbose_name = "Alvo de coleta"
        verbose_name_plural = "Alvos de coleta"

    def __str__(self):
        return f"{self.nome} - {self.get_coletor_display()}"