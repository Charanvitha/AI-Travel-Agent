import {describe,it,expect,vi} from 'vitest';
import {render,screen} from '@testing-library/react';
import App,{OverviewSummary} from './App';

describe('AtlasAI dashboard',()=>{
  it('shows the branded family travel landing dashboard',()=>{
    vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('offline')));
    render(<App/>);
    expect(screen.getByRole('heading',{name:/Your World/})).toBeTruthy();
    expect(screen.getByText('Plan a new trip')).toBeTruthy();
    vi.unstubAllGlobals();
  });
});

describe('trip overview',()=>{
  it('shows a day summary without itinerary time slots',()=>{
    const trip={startDate:'2027-01-10',endDate:'2027-01-11',budget:'12000',currency:'INR'};
    const itinerary={estimatedTotal:'1500',source:'Demo estimate',personalization:{travelPace:'relaxed'},warnings:[],days:[{dayNumber:1,date:'2027-01-10',estimatedDailyCost:'750',items:[{id:'1',title:'Pakhal Lake'}]},{dayNumber:2,date:'2027-01-11',estimatedDailyCost:'750',items:[{id:'2',title:'Warangal Fort'}]}]};
    render(<OverviewSummary trip={trip} itinerary={itinerary} onOpenItinerary={()=>{}}/>);
    expect(screen.getByText('Day-by-day snapshot')).toBeTruthy();
    expect(screen.getByText(/2 distinct place suggestions · relaxed pace/)).toBeTruthy();
    expect(screen.queryByText('09:00')).toBeNull();
  });
});
