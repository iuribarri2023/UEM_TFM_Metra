import test from 'node:test';
import assert from 'node:assert/strict';
import {humanizeTechnicalKey,humanizeTechnicalPath,esNumber,sourceTitle} from '../src/app/core/technical-terminology.ts';

test('Conservative Spanish mapping of real technical property names',()=>{
  assert.equal(humanizeTechnicalKey('thermal_transmittance'),'Transmitancia térmica');
  assert.equal(humanizeTechnicalKey('gwp_a1_a3_kgco2e_per_fu'),'Potencial de calentamiento global · A1–A3');
  assert.equal(humanizeTechnicalPath('technical_performance / thermal_resistance'),'Prestaciones técnicas / Resistencia térmica');
});

test('Spanish numeric formatting does not invent or convert units',()=>{
  assert.equal(esNumber(12345.25),'12.345,25');
  assert.equal(esNumber(Number.NaN),'—');
  assert.equal(humanizeTechnicalKey('unknown_measure_xyz'),'Unknown Measure Xyz');
});

test('Synthetic source is labelled unverified',()=>{
  assert.match(sourceTitle('DEMO_SIMULATED'),/Valor estimado/);
  assert.equal(sourceTitle('UNVERIFIED'),'No verificado');
});

import {comparableReference,referenceParts} from '../src/app/core/reference-model.ts';
test('Reference comparisons require identical units, scope and module coverage',()=>{
  const a={method:'METRA',scope:'scope',subsystem:'ENV.FAC',functional_unit:'m2',quantity:1,total:15,
    unit:'kg CO2e',indicator:'GWP',modules:[{module:'A1–A3',value:12},{module:'A4',value:3}]};
  assert.equal(comparableReference(a,{...a,total:16}),true);
  assert.equal(comparableReference(a,{...a,functional_unit:'ud'}),false);
  assert.equal(comparableReference(a,{...a,modules:a.modules.slice(0,1)}),false);
  assert.equal(referenceParts(a).reduce((sum,part)=>sum+part.value,0),15);
});
