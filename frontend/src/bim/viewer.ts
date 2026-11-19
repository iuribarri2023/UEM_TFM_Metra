/** Adapter for the scene and resources owned by one mounted IFC. */
import * as OBC from '@thatopen/components';
import {RenderedFaces} from '@thatopen/fragments';
import * as THREE from 'three';

export class IfcViewer {
  private components?: OBC.Components;
  private world?: OBC.SimpleWorld<OBC.SimpleScene,OBC.OrthoPerspectiveCamera,OBC.SimpleRenderer>;
  private manager?: OBC.FragmentsManager;
  private resize?: ResizeObserver;
  private stopped=false;
  private operations:Promise<unknown>=Promise.resolve();
  private bounds=new THREE.Box3();
  private planeId?:string;

  async mount(host:HTMLElement,bytes:Uint8Array,progress:(step:string)=>void){
    progress('Inicializando escena');
    const components=new OBC.Components();
    this.components=components;
    const world=components.get(OBC.Worlds).create<OBC.SimpleScene,OBC.OrthoPerspectiveCamera,OBC.SimpleRenderer>();
    this.world=world;
    world.scene=new OBC.SimpleScene(components);
    world.scene.setup();
    world.scene.three.background=new THREE.Color('#e7eeed');
    world.renderer=new OBC.SimpleRenderer(components,host);
    world.renderer.showLogo=false;
    world.camera=new OBC.OrthoPerspectiveCamera(components);
    await world.camera.controls.setLookAt(8,7,8,0,0,0);
    if(this.stopped)return;
    components.init();
    // Real orthographic projection supplied by the installed That Open camera.
    // Switching projection, not just moving the eye, avoids perspective foreshortening.
    await world.camera.projection.set('Orthographic');
    if(this.stopped)return;
    const fragments=components.get(OBC.FragmentsManager);
    this.manager=fragments;
    fragments.init(new URL('/bim/worker.mjs',location.origin).href);
    fragments.list.onItemSet.add(({value})=>{
      if(this.stopped)return;
      value.useCamera(world.camera.three);
      world.scene.three.add(value.object);
      void fragments.core.update(true).catch(()=>{});
    });
    world.camera.controls.addEventListener('update',()=>{
      if(!this.stopped)void fragments.core.update().catch(()=>{});
    });
    const resizeWorld=()=>{
      const {clientWidth:width,clientHeight:height}=host;
      if(this.stopped||!width||!height)return;
      world.renderer.resize(new THREE.Vector2(width,height));
      world.camera.updateAspect();
    };
    resizeWorld();
    this.resize=new ResizeObserver(resizeWorld);
    this.resize.observe(host);
    const loader=components.get(OBC.IfcLoader);
    progress('Cargando motor IFC');
    await loader.setup({autoSetWasm:false,wasm:{path:new URL('/bim/',location.origin).href,absolute:true}});
    if(this.stopped)return;
    progress('Convirtiendo geometría IFC');
    await loader.load(bytes,false,'authorized-ifc');
    if(this.stopped)return;
    const boxer=components.get(OBC.BoundingBoxer);
    boxer.list.clear();
    boxer.addFromModels();
    this.bounds.copy(boxer.get());
    boxer.list.clear();
    progress('Encuadrando modelo');
    await this.fit();
    // Axonometric eye on every new model; fit retains orthographic projection.
    await this.view('iso');
  }

  private enqueue(task:()=>Promise<void>){
    const operation=this.operations.then(async()=>{if(!this.stopped)await task()});
    this.operations=operation.catch(()=>{});
    return operation;
  }

  async pick(x:number,y:number){
    const world=this.world,manager=this.manager;
    if(this.stopped||!world||!manager)return null;
    const hit=await manager.raycast({camera:world.camera.three,mouse:new THREE.Vector2(x,y),dom:world.renderer.three.domElement});
    if(!hit||this.stopped)return null;
    return (await hit.fragments.getGuidsByLocalIds([hit.localId]))[0]||null;
  }

  select(guids:string[]){
    return this.enqueue(async()=>{
      const manager=this.manager;
      if(!manager)return;
      const ids=await manager.guidsToModelIdMap(guids);
      if(this.stopped)return;
      await manager.resetHighlight();
      if(this.stopped)return;
      if(Object.keys(ids).length)await manager.highlight({
        color:new THREE.Color('#b6f457'),renderedFaces:RenderedFaces.TWO,opacity:1,transparent:false
      },ids);
      if(!this.stopped)await manager.core.update(true);
    });
  }

  visibility(mode:'show-all'|'show'|'hide'|'isolate',guids:string[]=[]){
    return this.enqueue(async()=>{
      const components=this.components,manager=this.manager;
      if(!components||!manager)return;
      const hider=components.get(OBC.Hider);
      if(mode==='show-all'){await hider.set(true);return}
      const ids=await manager.guidsToModelIdMap(guids);
      if(this.stopped||!Object.keys(ids).length)return;
      if(mode==='isolate')await hider.isolate(ids);
      else await hider.set(mode==='show',ids);
    });
  }

  fit(guids:string[]=[]){
    return this.enqueue(async()=>{
      const world=this.world,manager=this.manager,components=this.components;
      if(!world||!manager||!components)return;
      const box=this.bounds.clone();
      if(guids.length){
        const ids=await manager.guidsToModelIdMap(guids);
        if(this.stopped)return;
        if(Object.keys(ids).length){
          const boxer=components.get(OBC.BoundingBoxer);
          boxer.list.clear();
          await boxer.addFromModelIdMap(ids);
          if(this.stopped)return;
          const selected=boxer.get();
          if(!selected.isEmpty())box.copy(selected);
          boxer.list.clear();
        }
      }
      if(!box.isEmpty())await world.camera.controls.fitToSphere(box.getBoundingSphere(new THREE.Sphere()),true);
      if(!this.stopped)await manager.core.update(true);
    });
  }

  view(preset:'iso'|'front'|'top'|'side'){
    return this.enqueue(async()=>{
      const world=this.world;
      if(!world||this.bounds.isEmpty())return;
      const center=this.bounds.getCenter(new THREE.Vector3());
      const radius=this.bounds.getBoundingSphere(new THREE.Sphere()).radius||1;
      const axes={iso:[1,.85,1],front:[0,0,1],top:[0,1,.001],side:[1,0,0]} as const;
      const eye=new THREE.Vector3(...axes[preset]).normalize().multiplyScalar(radius*3).add(center);
      await world.camera.controls.setLookAt(eye.x,eye.y,eye.z,center.x,center.y,center.z,true);
      if(!this.stopped)await world.camera.controls.fitToSphere(new THREE.Sphere(center,radius),true);
      if(!this.stopped)await this.manager?.core.update(true);
    });
  }

  section(percent:number|null){
    return this.enqueue(async()=>{
      const components=this.components,world=this.world;
      if(!components||!world)return;
      const clipper=components.get(OBC.Clipper);
      if(this.planeId){await clipper.delete(world,this.planeId);this.planeId=undefined}
      if(percent===null||this.stopped||this.bounds.isEmpty())return;
      const point=this.bounds.getCenter(new THREE.Vector3());
      point.y=THREE.MathUtils.lerp(this.bounds.min.y,this.bounds.max.y,percent/100);
      clipper.enabled=true;
      this.planeId=clipper.createFromNormalAndCoplanarPoint(world,new THREE.Vector3(0,-1,0),point);
      await this.manager?.core.update(true);
    });
  }

  dispose(){
    this.stopped=true;
    this.resize?.disconnect();
    this.components?.dispose();
    this.components=undefined;
    this.manager=undefined;
    this.world=undefined;
  }
}
