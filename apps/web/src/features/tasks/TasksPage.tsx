import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import api from '../../api/client';
import DataTable from '../../components/DataTable';
import Pagination from '../../components/Pagination';
import StatusBadge from '../../components/StatusBadge';
import LoadingState from '../../components/LoadingState';
import ErrorState from '../../components/ErrorState';
import EmptyState from '../../components/EmptyState';
import { useT } from '../../i18n';

const VIEWS=['all','attention','active','history'] as const;
const STATES=['created','queued','delivered','accepted','running','awaiting_approval','completed','failed','cancelled','expired','rejected'];
interface TaskRow { task_id:string; status:string; sender_agent:string; target_agent:string; created_at:string }
interface AgentRow { agent_id:string; name:string; agent_number:string }
const shortId=(value:string)=>value.length>14 ? value.slice(0,8)+'…'+value.slice(-4) : value;
export default function TasksPage() {
  const t=useT();
  const [params,setParams]=useSearchParams();
  const view=VIEWS.includes(params.get('view') as typeof VIEWS[number]) ? params.get('view')! : 'all';
  const status=params.get('status_filter') ?? '';
  const search=params.get('search') ?? '';
  const agentId=params.get('agent_id') ?? '';
  const [draft,setDraft]=useState(search);
  const [page,setPage]=useState(1);
  const limit=20;
  useEffect(()=>setDraft(search),[search]);
  const changeFilters=(patch:Record<string,string>)=>{
    const next=new URLSearchParams(params);
    Object.entries(patch).forEach(([key,value])=>value?next.set(key,value):next.delete(key));
    setPage(1); setParams(next,{replace:true});
  };
  const {data:roster}=useQuery({
    queryKey:['dashboard/agents','task-filter'],
    queryFn:()=>api.get<{agents:AgentRow[];total:number}>('/v1/dashboard/agents',{params:{page:1,page_size:200,order:'oldest'}}).then(r=>r.data),
  });
  const names=new Map((roster?.agents ?? []).map(a=>[a.agent_id,a.name]));
  const {data,isLoading,isError}=useQuery({
    queryKey:['tasks',page,limit,{view,status,search,agentId}],
    queryFn:()=>api.get<{tasks:TaskRow[];total:number}>('/v1/dashboard/tasks',{params:{
      offset:(page-1)*limit,limit,view,status_filter:status||undefined,search:search||undefined,agent_id:agentId||undefined,
    }}).then(r=>r.data),
  });
  const tasks=data?.tasks ?? [];
  const inputClass='border-2 border-pixel-line bg-pixel-surface px-3 min-h-[44px] text-pixel-fg font-pixel text-sm';
  return <div>
    <h2 className="font-display text-pixel-xl text-pixel-fg mb-6">{t('tasks.page.title')}</h2>
    <form className="task-filters" onSubmit={e=>{e.preventDefault();changeFilters({search:draft.trim()});}}>
      <label><span>{t('tasks.filter.view')}</span><select className={inputClass} aria-label={t('tasks.filter.view')} value={view} onChange={e=>changeFilters({view:e.target.value})}>
        {VIEWS.map(v=><option key={v} value={v}>{t('tasks.filter.view.'+v)}</option>)}
      </select></label>
      <label><span>{t('tasks.filter.status')}</span><select className={inputClass} aria-label={t('tasks.filter.status')} value={status} onChange={e=>changeFilters({status_filter:e.target.value})}>
        <option value="">{t('tasks.filter.anyStatus')}</option>
        {STATES.map(v=><option key={v} value={v}>{t('tasks.filter.status.'+v)}</option>)}
      </select></label>
      <label><span>{t('tasks.filter.agent')}</span><select className={inputClass} aria-label={t('tasks.filter.agent')} value={agentId} onChange={e=>changeFilters({agent_id:e.target.value})}>
        <option value="">{t('tasks.filter.anyAgent')}</option>
        {agentId && !names.has(agentId) && <option value={agentId}>{agentId.slice(0,8)}</option>}
        {(roster?.agents ?? []).map(a=><option key={a.agent_id} value={a.agent_id}>{a.name+' · '+a.agent_number}</option>)}
      </select></label>
      <label className="task-filters__search"><span>{t('tasks.filter.search')}</span><input className={inputClass} aria-label={t('tasks.filter.search')} maxLength={100} value={draft} onChange={e=>setDraft(e.target.value)} placeholder={t('tasks.filter.placeholder')}/></label>
      <button className={inputClass+' bg-pixel-accent text-[#191a26]'} type="submit">{t('tasks.filter.submit')}</button>
      <button className={inputClass} type="button" onClick={()=>{setPage(1);setDraft('');setParams({},{replace:true});}}>{t('tasks.filter.reset')}</button>
    </form>
    {roster && roster.total>200 && <p className="mb-3 text-pixel-muted text-sm">{t('tasks.filter.agentLimit')}</p>}
    <p className="mb-3 text-pixel-muted text-sm" aria-live="polite">{t('tasks.filter.total',{count:data?.total ?? 0})}</p>
    {isLoading ? <LoadingState/> : isError ? <ErrorState message={t('tasks.error.load')}/> : tasks.length===0 ?
      (!search && !status && !agentId && view==='all' ? <EmptyState scene="tasks" action={{to:'/docs/quickstart',label:t('tasks.empty.action.quickstart')}}/> : <EmptyState message={t('tasks.filter.empty')+' · '+t('tasks.filter.emptyHint')}/>) :
      <div className="task-table-panel bg-pixel-surface shadow-pixel-sm">
        <p className="md:hidden p-2 text-sm text-pixel-muted">{t('tasks.filter.scrollHint')}</p>
        <DataTable columns={[
          {key:'task_id',label:t('tasks.table.id'),render:(r:TaskRow)=><span className="font-mono" title={r.task_id}>{shortId(r.task_id)}</span>},
          {key:'details',label:'',render:(r:TaskRow)=><Link to={'/app/tasks/'+r.task_id} className="inline-flex items-center px-2 py-1 font-pixel text-pixel-sm bg-pixel-accent text-[#191a26] border-2 border-[#191a26] hover:underline">{t('tasks.table.view')}</Link>},
          {key:'status',label:t('tasks.table.status'),render:(r:TaskRow)=><StatusBadge status={r.status}/>},
          {key:'sender_agent',label:t('tasks.table.sender'),render:(r:TaskRow)=><span className="font-pixel" title={r.sender_agent}>{names.get(r.sender_agent)??shortId(r.sender_agent)}</span>},
          {key:'target_agent',label:t('tasks.table.target'),render:(r:TaskRow)=><span className="font-pixel" title={r.target_agent}>{names.get(r.target_agent)??shortId(r.target_agent)}</span>},
          {key:'created_at',label:t('tasks.table.created'),render:(r:TaskRow)=><span className="font-mono">{r.created_at}</span>},
        ]} data={tasks}/>
        <Pagination offset={(page-1)*limit} limit={limit} total={data?.total ?? 0} onPageChange={offset=>setPage(Math.floor(offset/limit)+1)}/>
      </div>}
  </div>;
}
