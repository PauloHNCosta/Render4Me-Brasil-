import bpy
import os
import sys # Importa o módulo sys para obter o caminho do executável do Blender

# Informações do Addon
bl_info = {
    "name": "Render4Me ! Brasil !", # Nome atualizado do addon
    "author": "Seu Nome", # Você pode mudar para o seu nome
    "version": (1, 5), # Versão atualizada
    "blender": (4, 0, 0), # Compatível com Blender 4.0 e superior
    "location": "3D Viewport > Sidebar (N-Panel)", # Nova localização do painel
    "description": "Gera comandos de linha para renderização de imagens/vídeos/cenas no Blender.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

# --- Propriedades para Cenas Individuais ---
# Esta classe define as propriedades para cada cena que o usuário adicionar
class BlenderSceneProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Nome da Cena (no .blend)",
        description="Nome exato da cena no arquivo Blender para renderizar",
        default=""
    )
    start_frame: bpy.props.IntProperty(
        name="Frame Inicial da Cena",
        description="Frame de início para a animação desta cena",
        default=1,
        min=1
    )
    end_frame: bpy.props.IntProperty(
        name="Frame Final da Cena",
        description="Frame de fim para a animação desta cena",
        default=250,
        min=1
    )

# --- Operador para Adicionar Cena ---
# Este operador cria uma nova entrada de cena na lista
class AddBlenderScene(bpy.types.Operator):
    bl_idname = "scene.add_blender_scene"
    bl_label = "Adicionar Cena"
    bl_description = "Adiciona uma nova entrada de cena para renderizar"

    def execute(self, context):
        context.scene.blender_render_props.scenes.add()
        return {'FINISHED'}

# --- Operador para Remover Cena ---
# Este operador remove uma entrada de cena da lista
class RemoveBlenderScene(bpy.types.Operator):
    bl_idname = "scene.remove_blender_scene"
    bl_label = "Remover Cena"
    bl_description = "Remover a entrada de cena selecionada"

    index: bpy.props.IntProperty() # Propriedade para saber qual cena remover

    def execute(self, context):
        context.scene.blender_render_props.scenes.remove(self.index)
        return {'FINISHED'}

# --- Operador para Gerar o Comando ---
# Este é o coração do addon, onde o comando de linha é construído
class GenerateBlenderCommand(bpy.types.Operator):
    bl_idname = "render.generate_blender_command"
    bl_label = "Gerar Comando de Render"
    bl_description = "Gera o(s) comando(s) de linha para renderização do Blender"

    def execute(self, context):
        props = context.scene.blender_render_props # Acessa as propriedades do addon

        # --- Preenchimento automático de caminhos se estiverem vazios ---
        if not props.blender_executable_path:
            # Usa bpy.app.binary_path para obter o caminho do executável do Blender
            if bpy.app.binary_path:
                props.blender_executable_path = bpy.app.binary_path
                self.report({'INFO'}, f"Caminho do Executável do Blender preenchido automaticamente: {bpy.app.binary_path}")
            else:
                self.report({'ERROR'}, "Não foi possível preencher automaticamente o Caminho do Executável do Blender. Por favor, defina-o manualmente.")
                return {'CANCELLED'}

        if not props.blend_file_path:
            if bpy.data.filepath:
                props.blend_file_path = bpy.data.filepath
                self.report({'INFO'}, f"Caminho do Arquivo .blend preenchido automaticamente: {bpy.data.filepath}")
            else:
                self.report({'ERROR'}, "O arquivo .blend atual não foi salvo. Por favor, salve o arquivo ou defina o Caminho do Arquivo .blend manualmente.")
                return {'CANCELLED'}
        # --- Fim do preenchimento automático ---

        blender_path = props.blender_executable_path
        blend_file_path = props.blend_file_path
        output_format = props.output_format
        custom_output_path = props.custom_output_path
        output_file_name = props.output_file_name
        video_codec = props.video_codec
        fps = props.fps
        render_engine = props.render_engine
        use_custom_render_engine = props.use_custom_render_engine

        # Validação de campos obrigatórios
        if not blender_path:
            self.report({'ERROR'}, "Por favor, defina o Caminho do Executável do Blender.")
            return {'CANCELLED'}
        if not blend_file_path:
            self.report({'ERROR'}, "Por favor, defina o Caminho do Arquivo .blend.")
            return {'CANCELLED'}

        # Normaliza os caminhos para uso em linha de comando (adiciona aspas se houver espaços)
        formatted_blender_path = f'"{blender_path}"' if ' ' in blender_path else blender_path
        formatted_blend_file_path = f'"{blend_file_path}"' if ' ' in blend_file_path else blend_file_path
        
        # O caminho de saída personalizado precisa ser tratado para ser um diretório
        # e ter barras corretas para o sistema operacional
        formatted_custom_output_path = ""
        if custom_output_path:
            # Garante que o caminho termina com o separador de diretório
            normalized_path = os.path.normpath(custom_output_path)
            if not normalized_path.endswith(os.sep):
                normalized_path += os.sep
            formatted_custom_output_path = f'"{normalized_path}"' if ' ' in normalized_path else normalized_path


        commands = [] # Lista para armazenar os comandos gerados

        # Adiciona o argumento do motor de renderização se ativado
        engine_arg = f"-E {render_engine}" if use_custom_render_engine else ""

        if props.use_scene_system:
            # Lógica para renderizar múltiplas cenas
            if not props.scenes:
                self.report({'ERROR'}, "Por favor, adicione pelo menos uma cena para renderizar ao usar o Sistema de Cenas.")
                return {'CANCELLED'}

            for scene_prop in props.scenes:
                if not scene_prop.name:
                    self.report({'ERROR'}, f"O nome da cena é obrigatório para a cena com Frame Inicial {scene_prop.start_frame}.")
                    commands = [] # Limpa comandos se houver erro
                    return {'CANCELLED'}
                if scene_prop.start_frame < 1:
                    self.report({'ERROR'}, f"Frame Inicial inválido para a cena '{scene_prop.name}'.")
                    commands = []
                    return {'CANCELLED'}
                if scene_prop.end_frame < scene_prop.start_frame:
                    self.report({'ERROR'}, f"Frame Final inválido para a cena '{scene_prop.name}'.")
                    commands = []
                    return {'CANCELLED'}

                command_base = f"{formatted_blender_path} -b {formatted_blend_file_path} -S {scene_prop.name}"
                output_path_arg = ""
                frame_args = ""
                video_args = ""

                if output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"]: # Formatos de imagem (sequência)
                    # Para sequências de imagem em animação, Blender usa -s -e -a
                    # O output_path_arg já inclui #### para preenchimento de frames
                    output_path_arg = f"-o {formatted_custom_output_path}render_{scene_prop.name}_####" if custom_output_path else f"-o //render_{scene_prop.name}_####"
                    frame_args = f"-s {scene_prop.start_frame} -e {scene_prop.end_frame} -a" # Renderiza a animação da cena como sequência de imagens
                else: # Formatos de vídeo
                    if not output_file_name:
                        self.report({'ERROR'}, "Nome do Arquivo de Saída é obrigatório para renderização de vídeo (configuração global).")
                        commands = []
                        return {'CANCELLED'}
                    
                    # Se houver custom_output_path, usa-o, senão usa o relativo ao .blend
                    output_path_arg = f"-o {formatted_custom_output_path}{output_file_name}_{scene_prop.name}" if custom_output_path else f"-o //{output_file_name}_{scene_prop.name}"
                    frame_args = f"-s {scene_prop.start_frame} -e {scene_prop.end_frame} -a" # -a para animação
                    
                    if video_codec:
                        video_args += f" -vcodec {video_codec}"
                    if fps:
                        video_args += f" -fps {fps}"
                
                commands.append(f"{command_base} {output_path_arg} -F {output_format} {frame_args}{video_args} {engine_arg}".strip())

        else: # Não usando o sistema de cenas (render global)
            command_base = f"{formatted_blender_path} -b {formatted_blend_file_path}"
            output_path_arg = ""
            frame_args = ""
            video_args = ""

            if output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"]: # Formatos de imagem
                # Se for render de imagem única, usa -f
                if props.frame_number < 1:
                    self.report({'ERROR'}, "Por favor, insira um Número de Frame válido (maior ou igual a 1) para a imagem.")
                    return {'CANCELLED'}
                # Se houver custom_output_path, usa-o, senão usa o relativo ao .blend
                output_path_arg = f"-o {formatted_custom_output_path}render_####" if custom_output_path else f"-o //render_####"
                frame_args = f"-f {props.frame_number}"
            else: # Formatos de vídeo
                if not output_file_name:
                    self.report({'ERROR'}, "Nome do Arquivo de Saída é obrigatório para renderização de vídeo.")
                    return {'CANCELLED'}
                if props.start_frame_global < 1:
                    self.report({'ERROR'}, "Por favor, insira um Frame Inicial Global válido.")
                    return {'CANCELLED'}
                if props.end_frame_global < props.start_frame_global:
                    self.report({'ERROR'}, "Por favor, insira um Frame Final Global válido (deve ser >= Frame Inicial).")
                    return {'CANCELLED'}

                # Se houver custom_output_path, usa-o, senão usa o relativo ao .blend
                output_path_arg = f"-o {formatted_custom_output_path}{output_file_name}" if custom_output_path else f"-o //{output_file_name}"
                frame_args = f"-s {props.start_frame_global} -e {props.end_frame_global} -a" # -a para animação
                
                if video_codec:
                    video_args += f" -vcodec {video_codec}"
                if fps:
                    video_args += f" -fps {fps}"
            
            commands.append(f"{command_base} {output_path_arg} -F {output_format} {frame_args}{video_args} {engine_arg}".strip())

        # Armazena o(s) comando(s) gerado(s) em uma propriedade para ser exibido na UI
        props.generated_command = "\n\n".join(commands)
        self.report({'INFO'}, "Comando(s) gerado(s) com sucesso!")
        return {'FINISHED'}

# --- Operador para Copiar Comando para a Área de Transferência ---
# Este operador copia o texto do comando para a área de transferência do sistema
class CopyBlenderCommand(bpy.types.Operator):
    bl_idname = "render.copy_blender_command"
    bl_label = "Copiar Comando"
    bl_description = "Copia o(s) comando(s) gerado(s) para a área de transferência"

    def execute(self, context):
        command_text = context.scene.blender_render_props.generated_command
        if command_text:
            context.window_manager.clipboard = command_text
            self.report({'INFO'}, "Comando(s) copiado(s) para a área de transferência!")
        else:
            self.report({'WARNING'}, "Nenhum comando para copiar.")
        return {'FINISHED'}

# --- Operador para Limpar Campos ---
# Este operador limpa os campos de texto do addon
class ClearBlenderFields(bpy.types.Operator):
    bl_idname = "render.clear_blender_fields"
    bl_label = "Limpar Campos"
    bl_description = "Limpa todos os campos de texto do addon"

    def execute(self, context):
        props = context.scene.blender_render_props
        props.blender_executable_path = ""
        props.blend_file_path = ""
        props.custom_output_path = ""
        props.output_file_name = ""
        props.video_codec = ""
        props.generated_command = ""
        # Não limpa os frames ou o formato, pois geralmente são valores que o usuário pode querer manter.
        # Se quiser limpar tudo, podemos adicionar mais campos aqui.
        self.report({'INFO'}, "Campos de texto limpos.")
        return {'FINISHED'}

# --- Operador para Doar (Mensagem Informativa) ---
class DonateBlenderAddon(bpy.types.Operator):
    bl_idname = "render.donate_blender_addon"
    bl_label = "Doar"
    bl_description = "Informações sobre doação para o desenvolvedor"

    def execute(self, context):
        self.report({'INFO'}, "Este addon é de graça e não tem que pagar! Obrigado pelo seu interesse.")
        return {'FINISHED'}

# --- Grupo de Propriedades Principal para o Addon ---
# Esta classe armazena todas as configurações do addon
class BlenderRenderProperties(bpy.types.PropertyGroup):
    blender_executable_path: bpy.props.StringProperty(
        name="Caminho do Executável do Blender",
        description="Caminho completo para o executável do Blender (ex: C:\\Program Files\\Blender Foundation\\Blender\\blender.exe). Será preenchido automaticamente se vazio.",
        subtype='FILE_PATH' # Isso adiciona um botão de navegador de arquivos
    )
    blend_file_path: bpy.props.StringProperty(
        name="Caminho do Arquivo .blend",
        description="Caminho completo para o arquivo .blend a ser renderizado. Será preenchido automaticamente com o arquivo atual se vazio.",
        subtype='FILE_PATH' # Isso adiciona um botão de navegador de arquivos
    )
    custom_output_path: bpy.props.StringProperty(
        name="Caminho da Pasta de Saída (Opcional)",
        description="Caminho completo para a pasta onde os renders serão salvos (deixe em branco para salvar na pasta do .blend).",
        subtype='DIR_PATH' # Isso adiciona um botão de navegador de diretórios
    )
    output_format: bpy.props.EnumProperty(
        name="Formato de Saída",
        description="Formato para a saída renderizada (imagem ou vídeo)",
        items=[
            ('PNG', "PNG", "Formato de imagem PNG"),
            ('JPEG', "JPEG", "Formato de imagem JPEG"),
            ('EXR', "OpenEXR", "Formato de imagem OpenEXR"),
            ('TIFF', "TIFF", "Formato de imagem TIFF"),
            ('BMP', "BMP", "Formato de imagem BMP"),
            ('AVI_JPEG', "AVI JPEG", "Vídeo AVI com compressão JPEG"),
            ('FFMPEG', "FFmpeg Video", "Formato de vídeo FFmpeg"),
            ('H264', "H.264", "Codec de vídeo H.264 (requer FFmpeg)"),
            ('MPEG', "MPEG", "Formato de vídeo MPEG"),
            ('OGV', "Ogg Theora", "Formato de vídeo Ogg Theora"),
        ],
        default='PNG'
    )
    frame_number: bpy.props.IntProperty(
        name="Número do Frame Único",
        description="Número do frame a renderizar para saída de imagem única",
        default=1,
        min=1
    )
    use_scene_system: bpy.props.BoolProperty(
        name="Usar Sistema de Cenas",
        description="Ativar para renderizar múltiplas cenas com ranges de frames específicos",
        default=False,
        # O 'update' força a interface a redesenhar, mostrando/ocultando campos
        update=lambda self, context: context.area.tag_redraw() 
    )
    output_file_name: bpy.props.StringProperty(
        name="Nome do Arquivo de Saída (para vídeo)",
        description="Nome base para o arquivo de vídeo de saída (ex: 'meu_video')",
        default="render"
    )
    start_frame_global: bpy.props.IntProperty(
        name="Frame Inicial da Animação (Global)",
        description="Frame de início para a renderização global da animação",
        default=1,
        min=1
    )
    end_frame_global: bpy.props.IntProperty(
        name="Frame Final da Animação (Global)",
        description="Frame de fim para a renderização global da animação",
        default=250,
        min=1
    )
    video_codec: bpy.props.StringProperty(
        name="Codec de Vídeo (Opcional)",
        description="Codec de vídeo específico (ex: libx264). Deixe em branco para o padrão do Blender.",
        default=""
    )
    fps: bpy.props.IntProperty(
        name="FPS (Opcional)",
        description="Frames por segundo para a saída de vídeo. Deixe em branco para o padrão do Blender.",
        min=1
    )
    # Coleção de propriedades para armazenar as configurações de cada cena
    scenes: bpy.props.CollectionProperty(type=BlenderSceneProperties)
    generated_command: bpy.props.StringProperty(
        name="Comando(s) Gerado(s)",
        description="O(s) comando(s) de linha gerado(s) para renderização",
        default="",
        subtype='NONE' # Exibe como texto simples, não como caminho de arquivo
    )
    # Nova propriedade para escolher o motor de renderização
    use_custom_render_engine: bpy.props.BoolProperty(
        name="Usar Motor de Render Personalizado",
        description="Ativar para especificar o motor de renderização (Cycles, Eevee, Workbench)",
        default=False,
        update=lambda self, context: context.area.tag_redraw()
    )
    render_engine: bpy.props.EnumProperty(
        name="Motor de Render",
        description="Escolha o motor de renderização",
        items=[
            ('CYCLES', "Cycles", "Renderiza com o Cycles"),
            ('EEVEE', "Eevee", "Renderiza com o Eevee"),
            ('WORKBENCH', "Workbench", "Renderiza com o Workbench"),
        ],
        default='CYCLES'
    )


# --- Painel da Interface do Usuário (UI) ---
# Esta classe define como o addon aparecerá na interface do Blender
class BlenderRenderPanel(bpy.types.Panel):
    bl_label = "Render4Me ! Brasil !" # Título do painel atualizado
    bl_idname = "VIEW3D_PT_blender_render_cli_generator" # ID único para o painel
    bl_space_type = 'VIEW_3D' # Onde o painel será exibido (na Viewport 3D)
    bl_region_type = 'UI' # Na região da UI (Sidebar ou N-Panel)
    bl_category = "CLI Render" # Nome da aba na Sidebar

    def draw(self, context):
        layout = self.layout # O layout é a área onde você adiciona os elementos da UI
        props = context.scene.blender_render_props # Acessa as propriedades do addon

        # Seção de Configurações Gerais
        box = layout.box()
        box.label(text="Configurações Gerais")
        box.prop(props, "blender_executable_path") # Campo com botão de busca de arquivo
        box.prop(props, "blend_file_path") # Campo com botão de busca de arquivo
        box.prop(props, "custom_output_path") # Campo com botão de busca de diretório
        box.prop(props, "output_format")

        # Opção para usar motor de render personalizado
        row = layout.row()
        row.prop(props, "use_custom_render_engine")
        if props.use_custom_render_engine:
            row = layout.row()
            row.prop(props, "render_engine")

        # Verifica o tipo de saída (imagem ou vídeo) para alternar campos
        selected_output_type = ('image' if props.output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"] else 'video')

        # Opção para usar o sistema de cenas
        row = layout.row()
        row.prop(props, "use_scene_system")

        if props.use_scene_system:
            # Seção do Sistema de Cenas
            box = layout.box()
            box.label(text="Cenas para Renderizar")
            # Itera sobre as cenas adicionadas e desenha seus campos
            for i, scene_prop in enumerate(props.scenes):
                scene_box = box.box()
                row = scene_box.row(align=True)
                row.prop(scene_prop, "name")
                # Botão para remover a cena
                row.operator("scene.remove_blender_scene", text="", icon='X').index = i
                scene_box.prop(scene_prop, "start_frame")
                scene_box.prop(scene_prop, "end_frame")
            # Botão para adicionar nova cena
            box.operator("scene.add_blender_scene", text="Adicionar Cena", icon='ADD')

            # Configurações de vídeo globais se o sistema de cenas estiver ativo e for vídeo
            if selected_output_type == 'video':
                box = layout.box()
                box.label(text="Configurações de Vídeo (Aplicam-se a todas as cenas)")
                box.prop(props, "output_file_name")
                box.prop(props, "video_codec")
                box.prop(props, "fps")

        else: # Não usando o sistema de cenas (render global)
            if selected_output_type == 'image':
                # Campos para render de imagem única
                box = layout.box()
                box.label(text="Configurações de Render de Imagem")
                box.prop(props, "frame_number")
            else: # Campos para render de vídeo global
                box = layout.box()
                box.label(text="Configurações de Render de Vídeo (Global)")
                box.prop(props, "output_file_name")
                box.prop(props, "start_frame_global")
                box.prop(props, "end_frame_global")
                box.prop(props, "video_codec")
                box.prop(props, "fps")

        # Botões para Gerar e Copiar o Comando
        row = layout.row(align=True)
        row.operator("render.generate_blender_command") # Botão "Gerar Comando de Render"
        row.operator("render.clear_blender_fields", icon='TRASH') # Botão "Limpar Campos" com ícone de lixeira
        
        # Exibe o comando gerado em um campo de texto não editável
        layout.prop(props, "generated_command", text="Comando(s) Gerado(s)")
        layout.operator("render.copy_blender_command") # Botão "Copiar Comando"

        # Botão de Doação
        layout.separator() # Adiciona um separador visual
        layout.operator("render.donate_blender_addon", icon='FUND') # Botão "Doar" com ícone de "FUND"

# Lista de classes a serem registradas/desregistradas no Blender
classes = (
    BlenderSceneProperties,
    AddBlenderScene,
    RemoveBlenderScene,
    GenerateBlenderCommand,
    CopyBlenderCommand,
    ClearBlenderFields,
    DonateBlenderAddon, # Adiciona a nova classe de operador
    BlenderRenderProperties,
    BlenderRenderPanel,
)

# --- Funções de Registro e Desregistro do Addon ---
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    # Cria um "pointer" para as propriedades do addon na cena atual do Blender
    bpy.types.Scene.blender_render_props = bpy.props.PointerProperty(type=BlenderRenderProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    # Remove o "pointer" das propriedades ao desativar o addon
    del bpy.types.Scene.blender_render_props

# Isso permite que o script seja executado diretamente no Blender para testes
if __name__ == "__main__":
    register()
