import {McpServer} from '@modelcontextprotocol/sdk/server/mcp.js';
import {StdioServerTransport} from '@modelcontextprotocol/sdk/server/stdio.js';
import {z} from 'zod';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';
const base=process.env.QUERYWORK_URL||'http://127.0.0.1:8766';
const token=process.env.QUERYWORK_TOKEN||readFileSync(resolve(fileURLToPath(new URL('..',import.meta.url)),'data/api-token'),'utf8').trim();
const server=new McpServer({name:'querywork',version:'1.0.0'});
async function call(path:string,body?:unknown){
 const r=await fetch(base+'/api/v1'+path,{method:body?'POST':'GET',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
 const data=await r.json();return {content:[{type:'text' as const,text:JSON.stringify(data)}],isError:!r.ok};
}
server.tool('create_experiment','Create a local search evaluation. Live mode uses paid APIs; demo mode uses fictional fixtures.',{original_search:z.string(),outcome:z.string(),requirements:z.array(z.string()).default([]),mode:z.enum(['demo','live']).default('demo')},async input=>call('/experiments',input));
server.tool('generate_terms','Generate three candidate queries; returns a job ID. Poll get_experiment for completion.',{experiment_id:z.string(),idempotency_key:z.string(),prompt_id:z.string().optional()},async ({experiment_id,...body})=>call(`/experiments/${experiment_id}/generate`,body));
server.tool('run_experiment','Search each candidate with Tavily and independently grade its results. Returns a job ID.',{experiment_id:z.string(),idempotency_key:z.string(),prompt_id:z.string().optional()},async ({experiment_id,...body})=>call(`/experiments/${experiment_id}/run`,body));
server.tool('get_experiment','Read saved queries, evidence, scores, and job states as a consistent snapshot.',{experiment_id:z.string()},async ({experiment_id})=>call('/experiments/'+experiment_id));
server.tool('refine_experiment','Use feedback to generate the next round, preserving the goal and rubric.',{experiment_id:z.string(),feedback:z.string(),idempotency_key:z.string(),prompt_id:z.string().optional()},async ({experiment_id,...body})=>call(`/experiments/${experiment_id}/refine`,body));
server.tool('optimize_experiment','Automatically generate, search, grade, and refine until the score target or explicit limits. Live mode uses paid APIs.',{experiment_id:z.string(),idempotency_key:z.string(),target_score:z.number().min(1).max(100).default(90),batch_size:z.union([z.literal(5),z.literal(10)]).default(5),max_rounds:z.number().int().min(1).max(100).optional(),max_queries:z.number().int().min(1).max(500).default(100)},async ({experiment_id,...body})=>call(`/experiments/${experiment_id}/optimize`,body));
await server.connect(new StdioServerTransport());

