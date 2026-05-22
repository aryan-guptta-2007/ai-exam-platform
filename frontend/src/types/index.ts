export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface Document {
  id: string;
  title: string;
  storage_path: string;
  owner_id: string;
  created_at: string;
}

export interface Question {
  id: string;
  exam_id: string;
  text: string;
  expected_answer: string;
  rubric: string;
  created_at: string;
}

export interface Exam {
  id: string;
  title: string;
  creator_id: string;
  document_id?: string;
  created_at: string;
  questions: Question[];
}

export interface TaskStatus {
  task_id: string;
  status: 'starting' | 'retrieving' | 'generating' | 'saving' | 'indexing' | 'saving_vectors' | 'done' | 'error';
  percentage: number;
  message: string;
}
