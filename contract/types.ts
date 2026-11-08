/* Generated from contract/schema.json by json-schema-to-typescript. DO NOT EDIT. Regenerate: make contract */

export type Version = string;
export type Event =
  | SwarmCreatedEvent
  | CallStateEvent
  | CallTranscriptEvent
  | CallExtractedEvent
  | SwarmRerouteEvent
  | SwarmKnowledgeEvent
  | SwarmRankedEvent
  | SwarmReservedEvent
  | SwarmCompletedEvent;
export type Seq = number;
export type SwarmId = string;
export type Ts = number;
export type Type = "swarm.created";
export type Query = string;
export type Mode = "live" | "simulated";
export type RawQuery = string;
export type Item = string;
export type Category = string;
export type Kind = "product" | "service" | "appointment" | "food" | "donation";
export type PlaceQuery = string;
export type Urgency = "now" | "today" | "flexible";
export type Priority = "balanced" | "price" | "distance" | "speed";
export type RadiusMiles = number;
export type Summary = string;
export type Lat = number;
export type Lng = number;
export type Id = string;
export type Name = string;
export type Address = string | null;
export type Phone = string | null;
export type Lat1 = number;
export type Lng1 = number;
export type DistanceMiles = number;
export type OpenNow = boolean | null;
export type Rating = number | null;
export type Tier = "primary" | "backup";
export type Source = "places" | "mock" | "demo" | "referral";
export type Targets = Target[];
export type Seq1 = number;
export type SwarmId1 = string;
export type Ts1 = number;
export type Type1 = "call.state";
export type CallId = string;
export type TargetId = string;
export type State = "queued" | "dialing" | "talking" | "extracting" | "completed" | "failed" | "cancelled";
export type Role = "inquiry" | "reserve";
export type Reason = string | null;
export type Seq2 = number;
export type SwarmId2 = string;
export type Ts2 = number;
export type Type2 = "call.transcript";
export type CallId1 = string;
export type TargetId1 = string;
export type UtteranceId = string;
export type Speaker = "agent" | "business";
export type Text = string;
export type IsFinal = boolean;
export type Seq3 = number;
export type SwarmId3 = string;
export type Ts3 = number;
export type Type3 = "call.extracted";
export type CallId2 = string;
export type TargetId2 = string;
export type Available = "yes" | "no" | "partial" | "unknown";
export type Item1 = string | null;
export type Price = number | null;
export type Currency = string;
export type Quantity = number | null;
export type CanHold = boolean | null;
export type WaitMinutes = number | null;
export type Alternatives = string[];
export type ReferralName = string | null;
export type ReferralPhone = string | null;
export type Closed = boolean | null;
export type Notes = string | null;
export type Confidence = number;
export type Hours = string | null;
export type Requirements = string | null;
export type Needs = string[];
export type PerishablesOk = boolean | null;
export type CanPickup = boolean | null;
export type Seq4 = number;
export type SwarmId4 = string;
export type Ts4 = number;
export type Type4 = "swarm.reroute";
export type FromCallId = string | null;
export type FromTargetId = string | null;
export type ToTargetId = string;
export type ToCallId = string;
export type Kind1 = "closed" | "no_stock" | "failed" | "referral" | "backup";
export type Reason1 = string;
export type Seq5 = number;
export type SwarmId5 = string;
export type Ts5 = number;
export type Type5 = "swarm.knowledge";
export type Note = string;
export type SourceCallId = string | null;
export type Seq6 = number;
export type SwarmId6 = string;
export type Ts6 = number;
export type Type6 = "swarm.ranked";
export type CallId3 = string;
export type TargetId3 = string;
export type Rank = number;
export type Score = number;
export type Reasons = string[];
export type Rankings = RankedItem[];
export type BestCallId = string | null;
export type Criteria = string;
export type Seq7 = number;
export type SwarmId7 = string;
export type Ts7 = number;
export type Type7 = "swarm.reserved";
export type CallId4 = string;
export type TargetId4 = string;
export type ReserveCallId = string;
export type Success = boolean;
export type Confirmation = string | null;
export type Message = string;
export type Seq8 = number;
export type SwarmId8 = string;
export type Ts8 = number;
export type Type8 = "swarm.completed";
export type Status = "completed" | "cancelled" | "error";
export type CallsMade = number;
export type CallsCompleted = number;
export type CallsFailed = number;
export type Positives = number;
export type ElapsedS = number;
export type Error = string | null;
export type Query1 = string;
export type Lat2 = number | null;
export type Lng2 = number | null;
export type RadiusMiles1 = number;
export type Mode1 = "live" | "simulated";
export type Priority1 = ("balanced" | "price" | "distance" | "speed") | null;
export type MaxCalls = number | null;
export type StopAfterMatches = number | null;
export type ContactName = string | null;
export type Purpose = "find" | "donate";
export type DonorAddress = string | null;
export type PickupBy = string | null;
export type UserId = string | null;
export type SwarmId9 = string;
export type Id1 = string;
export type Query2 = string;
export type Mode2 = "live" | "simulated";
export type Status1 = "running" | "completed" | "cancelled" | "error";
export type CreatedAt = number;
export type Events = (
  | SwarmCreatedEvent
  | CallStateEvent
  | CallTranscriptEvent
  | CallExtractedEvent
  | SwarmRerouteEvent
  | SwarmKnowledgeEvent
  | SwarmRankedEvent
  | SwarmReservedEvent
  | SwarmCompletedEvent
)[];
export type LastSeq = number;
export type Ok = boolean;
export type ReserveCallId1 = string;
export type Version1 = string;
export type LiveAvailable = boolean;
export type LiveMissing = string[];
export type LlmProvider = string;
export type PlacesProvider = "google" | "mock";
export type DemoTargets = number;

/**
 * Swarm Dial wire contract v1.0.0
 */
export interface ContractBundle {
  version?: Version;
  event: Event;
  create_swarm_request: CreateSwarmRequest;
  create_swarm_response: CreateSwarmResponse;
  swarm_detail: SwarmDetail;
  reserve_response: ReserveResponse;
  capabilities: Capabilities;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmCreatedEvent".
 */
export interface SwarmCreatedEvent {
  seq: Seq;
  swarm_id: SwarmId;
  ts: Ts;
  type: Type;
  data: SwarmCreatedData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmCreatedData".
 */
export interface SwarmCreatedData {
  query: Query;
  mode: Mode;
  intent: Intent;
  origin: LatLng;
  targets: Targets;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "Intent".
 */
export interface Intent {
  raw_query: RawQuery;
  item: Item;
  category: Category;
  kind: Kind;
  place_query: PlaceQuery;
  urgency?: Urgency;
  priority?: Priority;
  radius_miles: RadiusMiles;
  summary: Summary;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "LatLng".
 */
export interface LatLng {
  lat: Lat;
  lng: Lng;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "Target".
 */
export interface Target {
  id: Id;
  name: Name;
  address?: Address;
  phone?: Phone;
  lat: Lat1;
  lng: Lng1;
  distance_miles: DistanceMiles;
  open_now?: OpenNow;
  rating?: Rating;
  tier?: Tier;
  source?: Source;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallStateEvent".
 */
export interface CallStateEvent {
  seq: Seq1;
  swarm_id: SwarmId1;
  ts: Ts1;
  type: Type1;
  data: CallStateData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallStateData".
 */
export interface CallStateData {
  call_id: CallId;
  target_id: TargetId;
  state: State;
  role?: Role;
  reason?: Reason;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallTranscriptEvent".
 */
export interface CallTranscriptEvent {
  seq: Seq2;
  swarm_id: SwarmId2;
  ts: Ts2;
  type: Type2;
  data: CallTranscriptData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallTranscriptData".
 */
export interface CallTranscriptData {
  call_id: CallId1;
  target_id: TargetId1;
  utterance_id: UtteranceId;
  speaker: Speaker;
  text: Text;
  is_final: IsFinal;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallExtractedEvent".
 */
export interface CallExtractedEvent {
  seq: Seq3;
  swarm_id: SwarmId3;
  ts: Ts3;
  type: Type3;
  data: CallExtractedData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CallExtractedData".
 */
export interface CallExtractedData {
  call_id: CallId2;
  target_id: TargetId2;
  result: ExtractedResult;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "ExtractedResult".
 */
export interface ExtractedResult {
  available: Available;
  item?: Item1;
  price?: Price;
  currency?: Currency;
  quantity?: Quantity;
  can_hold?: CanHold;
  wait_minutes?: WaitMinutes;
  alternatives?: Alternatives;
  referral_name?: ReferralName;
  referral_phone?: ReferralPhone;
  closed?: Closed;
  notes?: Notes;
  confidence?: Confidence;
  hours?: Hours;
  requirements?: Requirements;
  needs?: Needs;
  perishables_ok?: PerishablesOk;
  can_pickup?: CanPickup;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmRerouteEvent".
 */
export interface SwarmRerouteEvent {
  seq: Seq4;
  swarm_id: SwarmId4;
  ts: Ts4;
  type: Type4;
  data: SwarmRerouteData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmRerouteData".
 */
export interface SwarmRerouteData {
  from_call_id?: FromCallId;
  from_target_id?: FromTargetId;
  to_target_id: ToTargetId;
  to_call_id: ToCallId;
  kind: Kind1;
  reason: Reason1;
  new_target?: Target | null;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmKnowledgeEvent".
 */
export interface SwarmKnowledgeEvent {
  seq: Seq5;
  swarm_id: SwarmId5;
  ts: Ts5;
  type: Type5;
  data: SwarmKnowledgeData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmKnowledgeData".
 */
export interface SwarmKnowledgeData {
  note: Note;
  source_call_id?: SourceCallId;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmRankedEvent".
 */
export interface SwarmRankedEvent {
  seq: Seq6;
  swarm_id: SwarmId6;
  ts: Ts6;
  type: Type6;
  data: SwarmRankedData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmRankedData".
 */
export interface SwarmRankedData {
  rankings: Rankings;
  best_call_id?: BestCallId;
  criteria: Criteria;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "RankedItem".
 */
export interface RankedItem {
  call_id: CallId3;
  target_id: TargetId3;
  rank: Rank;
  score: Score;
  reasons: Reasons;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmReservedEvent".
 */
export interface SwarmReservedEvent {
  seq: Seq7;
  swarm_id: SwarmId7;
  ts: Ts7;
  type: Type7;
  data: SwarmReservedData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmReservedData".
 */
export interface SwarmReservedData {
  call_id: CallId4;
  target_id: TargetId4;
  reserve_call_id: ReserveCallId;
  success: Success;
  confirmation?: Confirmation;
  message: Message;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmCompletedEvent".
 */
export interface SwarmCompletedEvent {
  seq: Seq8;
  swarm_id: SwarmId8;
  ts: Ts8;
  type: Type8;
  data: SwarmCompletedData;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmCompletedData".
 */
export interface SwarmCompletedData {
  status: Status;
  calls_made: CallsMade;
  calls_completed: CallsCompleted;
  calls_failed: CallsFailed;
  positives: Positives;
  elapsed_s: ElapsedS;
  error?: Error;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CreateSwarmRequest".
 */
export interface CreateSwarmRequest {
  query: Query1;
  lat?: Lat2;
  lng?: Lng2;
  radius_miles?: RadiusMiles1;
  mode?: Mode1;
  priority?: Priority1;
  max_calls?: MaxCalls;
  stop_after_matches?: StopAfterMatches;
  contact_name?: ContactName;
  purpose?: Purpose;
  donor_address?: DonorAddress;
  pickup_by?: PickupBy;
  user_id?: UserId;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "CreateSwarmResponse".
 */
export interface CreateSwarmResponse {
  swarm_id: SwarmId9;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmDetail".
 */
export interface SwarmDetail {
  swarm: SwarmSummary;
  events: Events;
  last_seq: LastSeq;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "SwarmSummary".
 */
export interface SwarmSummary {
  id: Id1;
  query: Query2;
  mode: Mode2;
  status: Status1;
  created_at: CreatedAt;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "ReserveResponse".
 */
export interface ReserveResponse {
  ok: Ok;
  reserve_call_id: ReserveCallId1;
}
/**
 * This interface was referenced by `ContractBundle`'s JSON-Schema
 * via the `definition` "Capabilities".
 */
export interface Capabilities {
  version: Version1;
  live_available: LiveAvailable;
  live_missing: LiveMissing;
  llm_provider: LlmProvider;
  places_provider: PlacesProvider;
  demo_targets: DemoTargets;
}
