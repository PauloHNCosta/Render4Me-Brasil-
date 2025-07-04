import bpy
import os
import sys
import shutil
import subprocess # Importa o módulo subprocess para executar comandos externos

# Informações do Addon
bl_info = {
    "name": "Render4Me ! Brasil !",
    "author": "Seu Nome",
    "version": (1, 9), # Versão atualizada para incluir o botão de iniciar/sair
    "blender": (4, 0, 0),
    "location": "3D Viewport > Sidebar (N-Panel)",
    "description": "Gera comandos de linha para renderização de imagens/vídeos/cenas no Blender.",
    "warning": "",
    "doc_url": "",
    "category": "Render",
}

# --- Propriedades para Cenas Individuais ---
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

# --- Propriedades para Câmeras Individuais ---
class BlenderCameraProperties(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(
        name="Nome da Câmera (no .blend)",
        description="Nome exato da câmera no arquivo Blender para renderizar",
        default=""
    )
    start_frame: bpy.props.IntProperty(
        name="Frame Inicial da Câmera",
        description="Frame de início para a animação desta câmera",
        default=1,
        min=1
    )
    end_frame: bpy.props.IntProperty(
        name="Frame Final da Câmera",
        description="Frame de fim para a animação desta câmera",
        default=250,
        min=1
    )

# --- Operador para Adicionar Cena ---
class AddBlenderScene(bpy.types.Operator):
    bl_idname = "scene.add_blender_scene"
    bl_label = "Adicionar Cena"
    bl_description = "Adiciona uma nova entrada de cena para renderizar"

    def execute(self, context):
        context.scene.blender_render_props.scenes.add()
        return {'FINISHED'}

# --- Operador para Remover Cena ---
class RemoveBlenderScene(bpy.types.Operator):
    bl_idname = "scene.remove_blender_scene"
    bl_label = "Remover Cena"
    bl_description = "Remover a entrada de cena selecionada"

    index: bpy.props.IntProperty()

    def execute(self, context):
        context.scene.blender_render_props.scenes.remove(self.index)
        return {'FINISHED'}

# --- Operador para Adicionar Câmera ---
class AddBlenderCamera(bpy.types.Operator):
    bl_idname = "camera.add_blender_camera"
    bl_label = "Adicionar Câmera"
    bl_description = "Adiciona uma nova entrada de câmera para renderizar"

    def execute(self, context):
        context.scene.blender_render_props.cameras.add()
        return {'FINISHED'}

# --- Operador para Remover Câmera ---
class RemoveBlenderCamera(bpy.types.Operator):
    bl_idname = "camera.remove_blender_camera"
    bl_label = "Remover Câmera"
    bl_description = "Remove a entrada de câmera selecionada"

    def execute(self, context):
        props = context.scene.blender_render_props
        cameras = props.cameras
        index = props.active_camera_index

        if 0 <= index < len(cameras):
            cameras.remove(index)
            if index > 0 and index == len(cameras):
                props.active_camera_index -= 1
        else:
            self.report({'WARNING'}, "Nenhuma câmera selecionada para remover.")
        
        return {'FINISHED'}

# --- Operador para Mover Câmera para Cima/Baixo ---
class BLENDER_RENDER_OT_cameras_move(bpy.types.Operator):
    bl_idname = "render.cameras_move"
    bl_label = "Mover Câmera"
    bl_description = "Move a câmera selecionada para cima ou para baixo na lista"

    direction: bpy.props.EnumProperty(items=[
        ('UP', "Para Cima", "Mover o item selecionado para cima"),
        ('DOWN', "Para Baixo", "Mover o item selecionado para baixo"),
    ])

    def execute(self, context):
        props = context.scene.blender_render_props
        cameras = props.cameras
        index = props.active_camera_index

        if len(cameras) == 0:
            return {'CANCELLED'}

        new_index = index
        if self.direction == 'UP':
            new_index = max(0, index - 1)
        elif self.direction == 'DOWN':
            new_index = min(len(cameras) - 1, index + 1)

        if new_index != index:
            cameras.move(index, new_index)
            props.active_camera_index = new_index
        
        return {'FINISHED'}

# --- Classe UIList para o Sistema de Câmeras (Permite Arrastar e Soltar) ---
class BLENDER_RENDER_UL_cameras(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_property):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            row = layout.row(align=True)
            row.prop(item, "name", text="", emboss=False, icon='CAMERA_DATA')
            row.prop(item, "start_frame", text="Início", emboss=False)
            row.prop(item, "end_frame", text="Fim", emboss=False)
        elif self.layout_type in {'GRID'}:
            layout.alignment = 'CENTER'
            layout.label(text="", icon='CAMERA_DATA')

# --- Operador para Gerar o Comando ---
class GenerateBlenderCommand(bpy.types.Operator):
    bl_idname = "render.generate_blender_command"
    bl_label = "Gerar Comando de Render"
    bl_description = "Gera o(s) comando(s) de linha para renderização do Blender"

    def execute(self, context):
        props = context.scene.blender_render_props

        if not props.blender_executable_path:
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

        blender_path = props.blender_executable_path
        blend_file_path = props.blend_file_path
        output_format = props.output_format
        custom_output_path = props.custom_output_path
        output_file_name = props.output_file_name
        video_codec = props.video_codec
        fps = props.fps
        render_engine = props.render_engine
        use_custom_render_engine = props.use_custom_render_engine

        if not blender_path:
            self.report({'ERROR'}, "Por favor, defina o Caminho do Executável do Blender.")
            return {'CANCELLED'}
        if not blend_file_path:
            self.report({'ERROR'}, "Por favor, defina o Caminho do Arquivo .blend.")
            return {'CANCELLED'}

        formatted_blender_path = f'"{blender_path}"' if ' ' in blender_path else blender_path
        formatted_blend_file_path = f'"{blend_file_path}"' if ' ' in blend_file_path else blend_file_path
        
        formatted_custom_output_path = ""
        if custom_output_path:
            normalized_path = os.path.normpath(custom_output_path)
            if not normalized_path.endswith(os.sep):
                normalized_path += os.sep
            formatted_custom_output_path = f'"{normalized_path}"' if ' ' in normalized_path else normalized_path


        commands = []
        engine_arg = f"-E {render_engine}" if use_custom_render_engine else ""

        if props.use_camera_system:
            if not props.cameras:
                self.report({'ERROR'}, "Por favor, adicione pelo menos uma câmera para renderizar ao usar o Sistema de Múltiplas Câmeras.")
                return {'CANCELLED'}

            for camera_prop in props.cameras:
                if not camera_prop.name:
                    self.report({'ERROR'}, f"O nome da câmera é obrigatório para a câmera com Frame Inicial {camera_prop.start_frame}.")
                    commands = []
                    return {'CANCELLED'}
                if camera_prop.start_frame < 1:
                    self.report({'ERROR'}, f"Frame Inicial inválido para a câmera '{camera_prop.name}'.")
                    commands = []
                    return {'CANCELLED'}
                if camera_prop.end_frame < camera_prop.start_frame:
                    self.report({'ERROR'}, f"Frame Final inválido para a câmera '{camera_prop.name}'.")
                    commands = []
                    return {'CANCELLED'}

                command_base = f"{formatted_blender_path} -b {formatted_blend_file_path} -c {camera_prop.name}"
                output_path_arg = ""
                frame_args = ""
                video_args = ""

                if output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"]:
                    output_path_arg = f"-o {formatted_custom_output_path}render_{camera_prop.name}_####" if custom_output_path else f"-o //render_{camera_prop.name}_####"
                    frame_args = f"-s {camera_prop.start_frame} -e {camera_prop.end_frame} -a"
                else:
                    if not output_file_name:
                        self.report({'ERROR'}, "Nome do Arquivo de Saída é obrigatório para renderização de vídeo (configuração global).")
                        commands = []
                        return {'CANCELLED'}
                    
                    output_path_arg = f"-o {formatted_custom_output_path}{output_file_name}_{camera_prop.name}" if custom_output_path else f"-o //{output_file_name}_{camera_prop.name}"
                    frame_args = f"-s {camera_prop.start_frame} -e {camera_prop.end_frame} -a"
                    
                    if video_codec:
                        video_args += f" -vcodec {video_codec}"
                    if fps:
                        video_args += f" -fps {fps}"
                
                commands.append(f"{command_base} {output_path_arg} -F {output_format} {frame_args}{video_args} {engine_arg}".strip())

        elif props.use_scene_system:
            if not props.scenes:
                self.report({'ERROR'}, "Por favor, adicione pelo menos uma cena para renderizar ao usar o Sistema de Cenas.")
                return {'CANCELLED'}

            for scene_prop in props.scenes:
                if not scene_prop.name:
                    self.report({'ERROR'}, f"O nome da cena é obrigatório para a cena com Frame Inicial {scene_prop.start_frame}.")
                    commands = []
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

                if output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"]:
                    output_path_arg = f"-o {formatted_custom_output_path}render_{scene_prop.name}_####" if custom_output_path else f"-o //render_{scene_prop.name}_####"
                    frame_args = f"-s {scene_prop.start_frame} -e {scene_prop.end_frame} -a"
                else:
                    if not output_file_name:
                        self.report({'ERROR'}, "Nome do Arquivo de Saída é obrigatório para renderização de vídeo (configuração global).")
                        commands = []
                        return {'CANCELLED'}
                    
                    output_path_arg = f"-o {formatted_custom_output_path}{output_file_name}_{scene_prop.name}" if custom_output_path else f"-o //{output_file_name}_{scene_prop.name}"
                    frame_args = f"-s {scene_prop.start_frame} -e {scene_prop.end_frame} -a"
                    
                    if video_codec:
                        video_args += f" -vcodec {video_codec}"
                    if fps:
                        video_args += f" -fps {fps}"
                
                commands.append(f"{command_base} {output_path_arg} -F {output_format} {frame_args}{video_args} {engine_arg}".strip())

        else:
            command_base = f"{formatted_blender_path} -b {formatted_blend_file_path}"
            output_path_arg = ""
            frame_args = ""
            video_args = ""

            if output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"]:
                if props.frame_number < 1:
                    self.report({'ERROR'}, "Por favor, insira um Número de Frame válido (maior ou igual a 1) para a imagem.")
                    return {'CANCELLED'}
                output_path_arg = f"-o {formatted_custom_output_path}render_####" if custom_output_path else f"-o //render_####"
                frame_args = f"-f {props.frame_number}"
            else:
                if not output_file_name:
                    self.report({'ERROR'}, "Nome do Arquivo de Saída é obrigatório para renderização de vídeo.")
                    return {'CANCELLED'}
                if props.start_frame_global < 1:
                    self.report({'ERROR'}, "Por favor, insira um Frame Inicial Global válido.")
                    return {'CANCELLED'}
                if props.end_frame_global < props.start_frame_global:
                    self.report({'ERROR'}, "Por favor, insira um Frame Final Global válido (deve ser >= Frame Inicial).")
                    return {'CANCELLED'}

                output_path_arg = f"-o {formatted_custom_output_path}{output_file_name}" if custom_output_path else f"-o //{output_file_name}"
                frame_args = f"-s {props.start_frame_global} -e {props.end_frame_global} -a"
                
                if video_codec:
                    video_args += f" -vcodec {video_codec}"
                if fps:
                    video_args += f" -fps {fps}"
            
            commands.append(f"{command_base} {output_path_arg} -F {output_format} {frame_args}{video_args} {engine_arg}".strip())

        props.generated_command = "\n\n".join(commands)
        self.report({'INFO'}, "Comando(s) gerado(s) com sucesso!")
        return {'FINISHED'}

# --- Operador para Copiar Comando para a Área de Transferência ---
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
        props.scenes.clear()
        props.cameras.clear()
        props.use_scene_system = False
        props.use_camera_system = False
        props.use_custom_render_engine = False
        self.report({'INFO'}, "Campos de texto e listas limpos.")
        return {'FINISHED'}

# --- Operador para Doar (Mensagem Informativa) ---
class DonateBlenderAddon(bpy.types.Operator):
    bl_idname = "render.donate_blender_addon"
    bl_label = "Doar"
    bl_description = "Informações sobre doação para o desenvolvedor"

    def execute(self, context):
        self.report({'INFO'}, "Este addon é de graça e não tem que pagar! Obrigado pelo seu interesse.")
        return {'FINISHED'}

# --- Operador para Atualizar o Addon ---
class UpdateBlenderAddon(bpy.types.Operator):
    bl_idname = "render.update_blender_addon"
    bl_label = "Atualizar Addon"
    bl_description = "Selecione o arquivo .py do addon atualizado para instalar"

    filepath: bpy.props.StringProperty(
        subtype='FILE_PATH',
        name="Arquivo de Atualização (.py)",
        description="Selecione o novo arquivo .py do addon para atualizar"
    )

    def execute(self, context):
        if not self.filepath:
            self.report({'ERROR'}, "Nenhum arquivo de atualização selecionado.")
            return {'CANCELLED'}

        current_addon_path = os.path.dirname(os.path.abspath(__file__))
        current_addon_file = os.path.join(current_addon_path, os.path.basename(__file__))
        
        if not self.filepath.lower().endswith(".py"):
            self.report({'ERROR'}, "O arquivo selecionado não é um arquivo Python (.py).")
            return {'CANCELLED'}

        try:
            shutil.copyfile(self.filepath, current_addon_file)
            self.report({'INFO'}, "Arquivo do addon atualizado com sucesso!")
            self.report({'INFO'}, "Para que as mudanças entrem em vigor, por favor, DESATIVE e REATIVE este addon (ou reinicie o Blender).")
        except Exception as e:
            self.report({'ERROR'}, f"Erro ao atualizar o addon: {e}. Verifique as permissões do arquivo.")
            return {'CANCELLED'}

        return {'FINISHED'}
    
    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

# --- NOVO: Operador para Iniciar Render e Fechar Blender ---
class StartBlenderRenderAndQuit(bpy.types.Operator):
    bl_idname = "render.start_and_quit"
    bl_label = "Iniciar Render e Sair do Blender"
    bl_description = "Fecha o Blender e inicia o(s) comando(s) de renderização no terminal."

    @classmethod
    def poll(cls, context):
        # O botão só estará ativo se houver um comando gerado
        return bool(context.scene.blender_render_props.generated_command)

    def invoke(self, context, event):
        # Exibe um diálogo de confirmação ao usuário
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        props = context.scene.blender_render_props
        
        if not props.generated_command:
            self.report({'ERROR'}, "Nenhum comando de renderização gerado. Por favor, gere o comando primeiro.")
            return {'CANCELLED'}

        # Divide os comandos em linhas individuais
        commands = props.generated_command.split("\n\n")

        # Determina o SO e a forma de encadear e executar os comandos
        if sys.platform.startswith('win'):
            # Windows: usa '&&' para encadear comandos no CMD
            # 'start cmd /k' abre uma nova janela do CMD e a mantém aberta após o comando
            chained_command = " && ".join(commands)
            # Adiciona um pause no final para o usuário ver a saída antes da janela fechar
            full_cmd = f'start cmd /k "{chained_command} & echo. & pause"'
            shell_exec = True # Precisa de shell=True para usar 'start'
        elif sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            # Linux/macOS: usa ';' para encadear comandos em bash
            chained_command = "; ".join(commands)
            if sys.platform.startswith('linux'):
                # Tenta abrir o gnome-terminal. Pode precisar de ajuste para outras distros/DEs
                full_cmd = f"gnome-terminal -- /bin/bash -c '{chained_command}; echo \"\\nRenderização concluída. Pressione Enter para fechar.\"; read -p \"\"'"
            else: # macOS
                # Usa osascript para abrir o Terminal.app
                full_cmd = f"osascript -e 'tell application \"Terminal\" to do script \"{chained_command}; echo \\\"\\nRenderização concluída. Pressione Enter para fechar.\\\"; read -p \\\"\\\"\"\"\"' & tell application \"Terminal\" to activate"
            shell_exec = True # Precisa de shell=True para osascript ou gnome-terminal serem encontrados no PATH
        else:
            self.report({'ERROR'}, "Sistema operacional não suportado para execução automática no terminal.")
            return {'CANCELLED'}

        try:
            # Importante: Aviso ao usuário sobre salvar o trabalho
            self.report({'INFO'}, "ATENÇÃO: Fechando o Blender e iniciando a renderização. Salve seu trabalho se necessário!")
            
            # Inicia o comando em um novo processo (não bloqueia o Blender)
            subprocess.Popen(full_cmd, shell=shell_exec)
            
            # Fecha o Blender (irá perguntar para salvar se houver mudanças não salvas)
            bpy.ops.wm.quit_blender()

        except Exception as e:
            self.report({'ERROR'}, f"Falha ao iniciar o render: {e}")
            return {'CANCELLED'}

        return {'FINISHED'}


# --- Grupo de Propriedades Principal para o Addon ---
class BlenderRenderProperties(bpy.types.PropertyGroup):
    blender_executable_path: bpy.props.StringProperty(
        name="Caminho do Executável do Blender",
        description="Caminho completo para o executável do Blender (ex: C:\\Program Files\\Blender Foundation\\Blender\\blender.exe). Será preenchido automaticamente se vazio.",
        subtype='FILE_PATH'
    )
    blend_file_path: bpy.props.StringProperty(
        name="Caminho do Arquivo .blend",
        description="Caminho completo para o arquivo .blend a ser renderizado. Será preenchido automaticamente com o arquivo atual se vazio.",
        subtype='FILE_PATH'
    )
    custom_output_path: bpy.props.StringProperty(
        name="Caminho da Pasta de Saída (Opcional)",
        description="Caminho completo para a pasta onde os renders serão salvos (deixe em branco para salvar na pasta do .blend).",
        subtype='DIR_PATH'
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
        update=lambda self, context: context.area.tag_redraw() 
    )
    use_camera_system: bpy.props.BoolProperty(
        name="Usar Sistema de Múltiplas Câmeras",
        description="Ativar para renderizar múltiplas câmeras com ranges de frames específicos",
        default=False,
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
    scenes: bpy.props.CollectionProperty(type=BlenderSceneProperties)
    cameras: bpy.props.CollectionProperty(type=BlenderCameraProperties)
    active_camera_index: bpy.props.IntProperty(
        name="Índice da Câmera Ativa",
        default=0,
        min=0
    )
    generated_command: bpy.props.StringProperty(
        name="Comando(s) Gerado(s)",
        description="O(s) comando(s) de linha gerado(s) para renderização",
        default="",
        subtype='NONE'
    )
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
class BlenderRenderPanel(bpy.types.Panel):
    bl_label = "Render4Me ! Brasil !"
    bl_idname = "VIEW3D_PT_blender_render_cli_generator"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "CLI Render"

    def draw(self, context):
        layout = self.layout
        props = context.scene.blender_render_props

        box = layout.box()
        box.label(text="Configurações Gerais")
        box.prop(props, "blender_executable_path")
        box.prop(props, "blend_file_path")
        box.prop(props, "custom_output_path")
        box.prop(props, "output_format")

        row = layout.row()
        row.prop(props, "use_custom_render_engine")
        if props.use_custom_render_engine:
            row = layout.row()
            row.prop(props, "render_engine")

        selected_output_type = ('image' if props.output_format in ["PNG", "JPEG", "EXR", "TIFF", "BMP"] else 'video')

        row = layout.row()
        row.prop(props, "use_scene_system")
        row = layout.row()
        row.prop(props, "use_camera_system")

        if props.use_camera_system:
            box = layout.box()
            box.label(text="Câmeras para Renderizar")

            row = box.row(align=True)
            col = row.column()
            col.template_list("BLENDER_RENDER_UL_cameras", "", props, "cameras", props, "active_camera_index", rows=5)

            col = row.column(align=True)
            col.operator("camera.add_blender_camera", icon='ADD', text="")
            col.operator("camera.remove_blender_camera", icon='REMOVE', text="")
            
            col.separator()
            col.operator("render.cameras_move", icon='TRIA_UP', text="").direction = 'UP'
            col.operator("render.cameras_move", icon='TRIA_DOWN', text="").direction = 'DOWN'

            if selected_output_type == 'video':
                box = layout.box()
                box.label(text="Configurações de Vídeo (Aplicam-se a todas as câmeras)")
                box.prop(props, "output_file_name")
                box.prop(props, "video_codec")
                box.prop(props, "fps")

        elif props.use_scene_system:
            box = layout.box()
            box.label(text="Cenas para Renderizar")
            for i, scene_prop in enumerate(props.scenes):
                scene_box = box.box()
                row = scene_box.row(align=True)
                row.prop(scene_prop, "name")
                row.operator("scene.remove_blender_scene", text="", icon='X').index = i
                scene_box.prop(scene_prop, "start_frame")
                scene_box.prop(scene_prop, "end_frame")
            box.operator("scene.add_blender_scene", text="Adicionar Cena", icon='ADD')

            if selected_output_type == 'video':
                box = layout.box()
                box.label(text="Configurações de Vídeo (Aplicam-se a todas as cenas)")
                box.prop(props, "output_file_name")
                box.prop(props, "video_codec")
                box.prop(props, "fps")

        else:
            if selected_output_type == 'image':
                box = layout.box()
                box.label(text="Configurações de Render de Imagem")
                box.prop(props, "frame_number")
            else:
                box = layout.box()
                box.label(text="Configurações de Render de Vídeo (Global)")
                box.prop(props, "output_file_name")
                box.prop(props, "start_frame_global")
                box.prop(props, "end_frame_global")
                box.prop(props, "video_codec")
                box.prop(props, "fps")

        row = layout.row(align=True)
        row.operator("render.generate_blender_command")
        row.operator("render.clear_blender_fields", icon='TRASH')
        
        layout.prop(props, "generated_command", text="Comando(s) Gerado(s)")
        layout.operator("render.copy_blender_command")

        # --- Botão NOVO: Iniciar Render e Sair do Blender ---
        layout.separator() # Separador para clareza visual
        row = layout.row()
        row.operator("render.start_and_quit", icon='PLAY') # Botão com ícone de Play
        # --- Fim do Botão NOVO ---

        box = layout.box()
        box.label(text="Manutenção do Addon")
        box.operator("render.update_blender_addon", icon='FILE_FOLDER')
        layout.operator("render.donate_blender_addon", icon='FUND')

# Lista de classes a serem registradas/desregistradas no Blender
classes = (
    BlenderSceneProperties,
    BlenderCameraProperties,
    AddBlenderScene,
    RemoveBlenderScene,
    AddBlenderCamera,
    RemoveBlenderCamera,
    BLENDER_RENDER_OT_cameras_move,
    BLENDER_RENDER_UL_cameras,
    GenerateBlenderCommand,
    CopyBlenderCommand,
    ClearBlenderFields,
    DonateBlenderAddon,
    UpdateBlenderAddon,
    StartBlenderRenderAndQuit, # Adiciona o novo operador aqui!
    BlenderRenderProperties,
    BlenderRenderPanel,
)

# --- Funções de Registro e Desregistro do Addon ---
def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.blender_render_props = bpy.props.PointerProperty(type=BlenderRenderProperties)

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.blender_render_props

if __name__ == "__main__":
    register()