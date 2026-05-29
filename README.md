# Mixamo Pessoal

Base das Fases 1 e 2: visualizador 3D, conversão para GLB, posicionamento de marcadores anatômicos e geração inicial de armature humanoide.

O sistema ainda não implementa câmera, MediaPipe, timeline, gravação de animação, autenticação, banco de dados ou exportação final. O skinning atual é apenas uma vinculação inicial simples para permitir exportar a armature com o mesh.

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
- `POST /api/rig`: recebe o nome do GLB convertido, os marcadores e o formato de exportação (`glb` ou `fbx`), cria uma armature e salva o arquivo rigado.
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
9. Clique em `Gerar Rig`.
10. Baixe o arquivo rigado pelo botão de download.

Se algum marcador obrigatório estiver pendente, o frontend mostra um aviso e bloqueia a geração do rig. O botão `Exportar JSON dos marcadores` continua disponível para debug.

## Gerar GLB rigado

1. Carregue um modelo e posicione todos os marcadores.
2. Em `Formato do rig`, selecione `GLB para preview`.
3. Clique em `Gerar Rig`.
4. O frontend carrega o GLB rigado no visualizador e habilita o download.

## Gerar FBX rigado

1. Carregue um modelo e posicione todos os marcadores.
2. Em `Formato do rig`, selecione `FBX para Unity/Blender`.
3. Clique em `Gerar Rig`.
4. O backend gera um GLB de preview e um FBX final.
5. O frontend carrega o GLB de preview e habilita o download do FBX.

## Conferir FBX na Unity

1. Baixe o arquivo `.fbx` gerado.
2. Arraste o FBX para a pasta `Assets` do projeto Unity.
3. Selecione o asset importado no Project.
4. Na aba `Rig`, confira a armature e configure o tipo conforme o teste desejado.
5. Expanda o prefab/modelo importado na cena ou no inspector para verificar os bones, incluindo `Hips`, `Spine`, `Chest`, `Head`, `LeftUpperArm`, `RightUpperLeg` e demais nomes humanoides.

## Coordenadas dos marcadores

Os marcadores são capturados no Three.js em coordenadas glTF, com `Y` como eixo vertical. Ao importar o GLB no Blender, o modelo passa para o espaço interno Z-up do Blender. O script `generate_rig.py` converte cada marcador assim:

```text
Three/glTF (x, y, z) -> Blender (x, -z, y)
```

Essa conversão prioriza colocar o esqueleto aproximadamente no mesmo lugar do personagem. Orientação fina de bones e compatibilidade humanoide completa ficam para as próximas fases.

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
- A armature é gerada com hierarquia humanoide inicial, mas o ajuste fino de orientação dos bones ainda é básico.
- O skinning automático completo ainda não está implementado; o script cria uma vinculação simples por proximidade para teste.
- Não há animação, captura por câmera, MediaPipe ou timeline.

## Próxima fase

Fase 3 deve focar em skinning automático mais robusto, pesos por região anatômica, melhor orientação dos bones, validação de pose T/A e preparação mais completa para uso como rig humanoide.
