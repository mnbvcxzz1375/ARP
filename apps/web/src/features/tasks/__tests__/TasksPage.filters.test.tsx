import { it, expect, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import TasksPage from '../TasksPage';
import api from '../../../api/client';
vi.mock('../../../api/client',()=>({default:{get:vi.fn()}}));
it('keeps filters usable for empty results and sends view/search to the server', async()=>{
  vi.mocked(api.get).mockImplementation(async(url)=>({data:String(url).includes('/agents')?{agents:[],total:0}:{tasks:[],total:0}}) as never);
  render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><TasksPage/></MemoryRouter></QueryClientProvider>);
  const view=await screen.findByRole('combobox',{name:'Task view'});
  fireEvent.change(view,{target:{value:'active'}});
  await waitFor(()=>expect(api.get).toHaveBeenCalledWith('/v1/dashboard/tasks',expect.objectContaining({params:expect.objectContaining({view:'active'})})));
  fireEvent.change(screen.getByRole('textbox',{name:'Search tasks'}),{target:{value:'Atlas'}});
  fireEvent.click(screen.getByRole('button',{name:'Search'}));
  await waitFor(()=>expect(api.get).toHaveBeenCalledWith('/v1/dashboard/tasks',expect.objectContaining({params:expect.objectContaining({search:'Atlas',offset:0})})));
  expect(screen.getByRole('combobox',{name:'Task view'})).toBeInTheDocument();
});
