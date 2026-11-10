import {Client} from '@modelcontextprotocol/sdk/client/index.js';
import {StdioClientTransport} from '@modelcontextprotocol/sdk/client/stdio.js';
import {resolve} from 'node:path';
import assert from 'node:assert/strict';
const transport=new StdioClientTransport({command:process.execPath,args:[resolve('node_modules/tsx/dist/cli.mjs'),resolve('mcp/server.ts')]});
const client=new Client({name:'querywork-smoke-test',version:'1.0.0'});
await client.connect(transport);
try{
 const tools=await client.listTools();assert.equal(tools.tools.length,6);
 async function call(name:string,args:Record<string,unknown>){const result=await client.callTool({name,arguments:args});assert.ok(!result.isError,JSON.stringify(result));return JSON.parse((result.content as {text:string}[])[0].text);}
 const e=await call('create_experiment',{original_search:'MCP demo search',outcome:'Find local wholesale suppliers',requirements:['Wholesale'],mode:'demo'});
 async function wait(){for(let i=0;i<100;i++){const data=await call('get_experiment',{experiment_id:e.id});const state=data.job_states.at(-1);if(state&&!['queued','running'].includes(state.status)){assert.equal(state.status,'complete',state.stage);return data;}await new Promise(r=>setTimeout(r,100));}throw Error('MCP job timed out');}
 await call('generate_terms',{experiment_id:e.id,idempotency_key:crypto.randomUUID()});await wait();
 await call('run_experiment',{experiment_id:e.id,idempotency_key:crypto.randomUUID()});const data=await wait();assert.equal(data.rounds[0].queries.length,4);assert.equal(data.rounds[0].queries[0].status,'complete');
 await call('refine_experiment',{experiment_id:e.id,feedback:'Try product terminology',idempotency_key:crypto.randomUUID()});assert.equal((await wait()).rounds.length,2);
 await call('optimize_experiment',{experiment_id:e.id,idempotency_key:crypto.randomUUID(),target_score:100,max_rounds:1,max_queries:20,batch_size:5});assert.equal((await wait()).optimization.stop_reason,'round_limit');
 console.log('MCP tools verified: create, generate, run, inspect, refine, optimize share the local API and database.');
}finally{await client.close();}
