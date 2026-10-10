const fs=require('fs');const path=require('path');
const katex=require('../docs/mathematical_report/vendor/katex/katex.cjs');
const eq=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const macros={'\\Tr':'\\operatorname{Tr}','\\tr':'\\operatorname{Tr}','\\diag':'\\operatorname{diag}','\\rank':'\\operatorname{rank}','\\ket':'\\left|#1\\right\\rangle','\\bra':'\\left\\langle#1\\right|','\\norm':'\\left\\lVert#1\\right\\rVert','\\argmin':'\\operatorname*{arg\\,min}','\\argmax':'\\operatorname*{arg\\,max}','\\Var':'\\operatorname{Var}','\\Cov':'\\operatorname{Cov}','\\Haf':'\\operatorname{Haf}','\\Span':'\\operatorname{span}'};
const errors=[];const result=eq.map(e=>{try{return {...e,html:katex.renderToString(e.latex,{displayMode:e.display,throwOnError:true,strict:'warn',trust:false,output:'htmlAndMathml',macros})};}catch(err){errors.push({id:e.id,latex:e.latex,message:String(err)});return{...e,html:''}}});
fs.writeFileSync(process.argv[3],JSON.stringify(result));fs.writeFileSync(path.join(path.dirname(process.argv[3]),'math_errors.json'),JSON.stringify(errors,null,2));
console.log(JSON.stringify({math:result.length,errors:errors.length}));if(errors.length)process.exit(2);
