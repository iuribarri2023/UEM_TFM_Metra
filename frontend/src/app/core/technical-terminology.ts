/** Conservative display dictionary: NO units are inferred from a property name. */
export const TECHNICAL_LABELS:Record<string,string>={
 thermal_transmittance:'Transmitancia térmica', thermal_resistance:'Resistencia térmica',
 surface_mass:'Masa superficial', fire_resistance:'Resistencia al fuego',
 airborne_sound_insulation:'Aislamiento a ruido aéreo',total_thickness_mm:'Espesor total',
 thickness:'Espesor',nominal_power_kw:'Potencia nominal',module_area_m2:'Superficie del módulo',
 illustrative_mass_kg_per_fu:'Masa ilustrativa por unidad funcional',
 gwp_a1_a3_kgco2e_per_fu:'Potencial de calentamiento global · A1–A3',
 gwp:'Potencial de calentamiento global',gwp_total:'Potencial de calentamiento global total',
 economic_performance:'Comportamiento económico',environmental_performance:'Comportamiento ambiental',
 energy_performance:'Comportamiento energético',industrialization_performance:'Industrialización',
 technical_performance:'Prestaciones técnicas',normalization_inputs:'Referencias de normalización',
 unit_construction_cost:'Coste unitario de construcción',unit_cost:'Coste unitario',
 cost:'Coste',currency:'Moneda',materials:'Materiales',labour:'Mano de obra',assembly:'Montaje',
 transport:'Transporte',quantity:'Cantidad',density:'Densidad',mass:'Masa',strength:'Resistencia',
 source_value:'Valor de referencia',source_reference:'Fuente de referencia',value_basis:'Base del valor',
 calculation_result:'Resultado de cálculo',assessment_status:'Estado de evaluación',
 value_status:'Estado del valor',functional_unit:'Unidad funcional',
 standard:'Norma',material:'Material',name:'Nombre',description:'Descripción',
 energy_data:'Información energética',legacy:'Datos históricos',unit:'Unidad',
 recycled_content:'Contenido reciclado',primary_energy:'Energía primaria',water_use:'Uso de agua',
 waste:'Residuos', module:'Módulo', indicator:'Indicador', source_type:'Tipo de procedencia'
};
export function humanizeTechnicalKey(key:string):string {
  if(TECHNICAL_LABELS[key])return TECHNICAL_LABELS[key];
  return key.replace(/_kgco2e_/g,' · kg CO₂ eq. / ').replace(/_/g,' ').replace(/\b\w/g,letter=>letter.toUpperCase());
}
export function humanizeTechnicalPath(path:string):string {
  return path.split(' / ').map(humanizeTechnicalKey).join(' / ');
}
export function esNumber(number:number,maxDecimals=4):string {
  return Number.isFinite(number)?new Intl.NumberFormat('es-ES',{maximumFractionDigits:maxDecimals}).format(number):'—';
}
export function sourceTitle(value:string):string {
  const sources:Record<string,string>={DEMO_SIMULATED:'Valor estimado',
    UNVERIFIED:'No verificado',provisional_poc_assumption:'Hipótesis provisional PoC',
    simulated_source_workbook:'Fuente simulada del estudio',sourced_legacy_catalogue:'Catálogo histórico',
    manufacturer_declared:'Declarado por fabricante'};
  return sources[value]||value;
}
