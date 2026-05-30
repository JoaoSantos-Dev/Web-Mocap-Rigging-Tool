# Mixamo Pessoal

Base das Fases 1, 2, 2.5 e 3: visualizador 3D, conversão para GLB, posicionamento de marcadores anatômicos, geração de armature humanoide e skinning automático básico.

O sistema ainda não implementa câmera, MediaPipe, timeline, gravação de animação por vídeo, retarget, autenticação, banco de dados ou exportação final.

## Requisitos

- Python 3.10+
- Node.js 18+
- Blender instalado e disponível no PATH como `blender`

Se o Blender não estiver no PATH, defina a variável `BLENDER_PATH` apontando para o executável.

## Rodar o backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints principais:

- `POST /api/convert`: recebe `.obj`, `.fbx`, `.glb` ou `.gltf`, chama o Blender headless e gera um `.glb`.
- `POST /api/rig`: recebe o nome do GLB convertido, os marcadores e o formato de exportação (`glb` ou `fbx`), cria uma armature, aplica automatic weights e salva o arquivo rigado.
- `GET /api/models/{filename}`: serve o GLB convertido.
- `GET /api/rigged/{filename}`: serve arquivos rigados `.glb` ou `.fbx`.

## Rodar o frontend

```bash
cd frontend
npm install
npm run dev
```

Por padrão, o frontend usa `http://localhost:8000` como backend. Para alterar:

```bash
VITE_API_BASE_URL=http://localhost:8000 npm run dev
```

## Testar com um modelo 3D

1. Abra o frontend em `http://localhost:5173`.
2. Selecione um arquivo `.obj`, `.fbx`, `.glb` ou `.gltf`.
3. Clique em `Converter e carregar`.
4. Aguarde o backend converter o arquivo para GLB.
5. Selecione um marcador, por exemplo `Queixo`.
6. Clique no mesh do personagem para posicionar a esfera do marcador.
7. Posicione todos os marcadores obrigatórios.
8. Escolha `GLB para preview` ou `FBX para Unity/Blender`.
9. Clique em `Gerar Rig com Skinning`.
10. Baixe o arquivo rigado pelo botão de download.

Se algum marcador obrigatório estiver pendente, o frontend mostra um aviso e bloqueia a geração do rig. O botão `Exportar JSON dos marcadores` continua disponível para debug.

## Gerar GLB rigado

1. Carregue um modelo e posicione todos os marcadores.
2. Em `Formato do rig`, selecione `GLB para preview`.
3. Clique em `Gerar Rig com Skinning`.
4. O frontend carrega o GLB rigado no visualizador e inicia o download.

## Gerar FBX rigado

1. Carregue um modelo e posicione todos os marcadores.
2. Em `Formato do rig`, selecione `FBX para Unity/Blender`.
3. Clique em `Gerar Rig com Skinning`.
4. O backend gera um GLB de preview e um FBX final.
5. O frontend carrega o GLB de preview, inicia o download do FBX e mantém um link para baixar o GLB.

## Conferir FBX na Unity

1. Baixe o arquivo `.fbx` gerado.
2. Arraste o FBX para a pasta `Assets` do projeto Unity.
3. Selecione o asset importado no Project.
4. Na aba `Rig`, configure como `Generic` para o teste inicial.
5. Expanda o prefab/modelo importado na cena ou no inspector para verificar os bones, incluindo `Hips`, `Spine`, `Chest`, `Head`, `LeftUpperArm`, `RightUpperLeg` e demais nomes humanoides.
6. Arraste o modelo para a cena, selecione um bone e rotacione no editor. Se o skinning funcionou, a malha acompanha o bone.

## Conferir no Blender

1. Abra o `.glb` ou `.fbx` rigado no Blender.
2. Selecione o mesh e verifique se existe um `Armature Modifier` apontando para `Humanoid_Armature`.
3. Na aba de dados do mesh, confira os vertex groups com nomes dos bones.
4. Selecione a armature, entre em `Pose Mode` e rotacione um bone.
5. A malha deve acompanhar o movimento, ainda que com deformação simples.
6. A action `Rig_Deformation_Test` é exportada para facilitar a verificação de braço e perna esquerdos.

## Coordenadas dos marcadores

Os marcadores são capturados no Three.js em coordenadas glTF, com `Y` como eixo vertical. Ao importar o GLB no Blender, o modelo passa para o espaço interno Z-up do Blender. O script `generate_rig.py` converte cada marcador assim:

```text
Three/glTF (x, y, z) -> Blender (x, -z, y)
```

Essa conversão prioriza colocar o esqueleto aproximadamente no mesmo lugar do personagem. Orientação fina de bones e compatibilidade humanoide completa ficam para as próximas fases.

## Refinamentos da Fase 2.5 e Fase 3

- O mesh importado é normalizado para world space antes do bind, deixando escala `1,1,1` e rotação zerada quando possível.
- Os pontos de tronco, peito, pescoço, cabeça, quadris, mãos e pés são derivados dos marcadores com proporções mais previsíveis.
- Bones sequenciais são conectados no Blender quando os pontos coincidem sem deslocar o osso.
- O script recalcula bone roll com `GLOBAL_POS_Y`, com fallback para `GLOBAL_POS_Z`.
- O script aplica `bpy.ops.object.parent_set(type='ARMATURE_AUTO')`, equivalente a `Armature Deform With Automatic Weights`.
- O script valida `Armature Modifier`, vertex groups e grupos com pesos.
- O FBX é exportado com `add_leaf_bones=False`, `apply_unit_scale=True`, `use_space_transform=True` e somente `ARMATURE` + `MESH`.
- Se a action de teste existir, o FBX sai com `bake_anim=True`.
- A action `Rig_Deformation_Test` tem keyframes simples para braço e perna esquerdos.
- O endpoint retorna `skinningApplied`, `meshCount`, `vertexGroups`, `weightedVertexGroups`, `warnings` e `actions`.

## Marcadores obrigatórios

A interface mostra os nomes em português. O JSON exportado preserva as chaves técnicas abaixo:

| Nome na interface | Chave no JSON |
| --- | --- |
| Queixo | `chin` |
| Pelve | `pelvis` |
| Ombro esquerdo | `leftShoulder` |
| Ombro direito | `rightShoulder` |
| Cotovelo esquerdo | `leftElbow` |
| Cotovelo direito | `rightElbow` |
| Punho esquerdo | `leftWrist` |
| Punho direito | `rightWrist` |
| Joelho esquerdo | `leftKnee` |
| Joelho direito | `rightKnee` |
| Tornozelo esquerdo | `leftAnkle` |
| Tornozelo direito | `rightAnkle` |

O JSON exportado segue este formato:

```json
{
  "markers": {
    "chin": { "x": 0, "y": 1.75, "z": 0 },
    "pelvis": { "x": 0, "y": 0.95, "z": 0 }
  }
}
```

## Limitações atuais

- Arquivos `.gltf` e `.obj` são enviados como arquivo único; dependências externas como `.bin`, `.mtl` e texturas separadas podem não estar disponíveis para o Blender.
- Os marcadores ficam apenas em memória no navegador até a exportação do JSON.
- A centralização e o enquadramento são básicos, baseados na bounding box do modelo.
- A armature é gerada com hierarquia humanoide inicial, mas o ajuste fino de orientação dos bones ainda pode precisar de refinamento.
- O skinning usa automatic weights do Blender. Ele cria deformação real, mas ainda pode produzir pesos ruins em ombros, virilha, joelhos, cotovelos, roupas e acessórios.
- Modelos com múltiplas malhas são processados, mas o MVP tende a funcionar melhor com malha única.
- A conexão visual de bones pode não ser preservada do mesmo jeito quando o FBX é reimportado no Blender/Unity, mas a hierarquia e os nomes são exportados sem leaf bones extras.
- Não há animação, captura por câmera, MediaPipe ou timeline.

## Próxima fase

Fase 4 deve focar em refinamento de pesos por região anatômica, ferramentas de diagnóstico de deformação, melhor suporte a roupas/acessórios, validação de pose T/A e preparação mais completa para retarget/animação.
