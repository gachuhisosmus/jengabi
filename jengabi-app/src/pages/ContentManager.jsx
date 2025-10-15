import React, { useState, useEffect } from 'react'
import { useSupabase } from '../contexts/SupabaseContext'
import { 
  Plus, 
  Calendar, 
  Hash, 
  Image, 
  Video,
  Zap
} from 'lucide-react'

const ContentManager = () => {
  const { user, supabase } = useSupabase()
  const [tasks, setTasks] = useState([])
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [newTask, setNewTask] = useState({
    title: '',
    type: 'post',
    platform: 'instagram',
    due_date: '',
    description: ''
  })

  useEffect(() => {
    fetchContentTasks()
  }, [])

  const fetchContentTasks = async () => {
    // Mock data for now
    setTasks([
      {
        id: 1,
        title: 'Product Launch Post',
        type: 'post',
        platform: 'instagram',
        due_date: '2024-01-15',
        status: 'pending'
      },
      {
        id: 2,
        title: 'Weekly Update Story',
        type: 'story',
        platform: 'facebook',
        due_date: '2024-01-16',
        status: 'in_progress'
      }
    ])
  }

  const createTask = async () => {
    // For now, just add to local state
    const newTaskObj = {
      id: Date.now(),
      ...newTask,
      status: 'pending'
    }
    setTasks([...tasks, newTaskObj])
    setShowCreateModal(false)
    setNewTask({
      title: '',
      type: 'post',
      platform: 'instagram',
      due_date: '',
      description: ''
    })
  }

  const generateHashtags = async () => {
    return ['#AfricanBusiness', '#SupportLocal', '#MadeInAfrica']
  }

  const generateAIContent = async () => {
    // Mock AI content generation
    const content = "Exciting news! We're launching our new product line designed specifically for African creators. Stay tuned for more updates! #AfricanCreators #NewLaunch"
    setNewTask(prev => ({ ...prev, description: content }))
  }

  return (
    <div className="space-y-6">
      <div className="sm:flex sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Content Manager</h1>
          <p className="mt-2 text-sm text-gray-700">
            Plan, create, and schedule your content across all platforms
          </p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="inline-flex items-center px-4 py-2 border border-transparent text-sm font-medium rounded-md shadow-sm text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
        >
          <Plus className="h-4 w-4 mr-2" />
          New Content
        </button>
      </div>

      {/* Content Calendar View */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            Content Calendar
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-7">
            {tasks.map(task => (
              <div key={task.id} className={`p-3 border rounded-lg ${
                task.platform === 'instagram' ? 'border-pink-200 bg-pink-50' :
                task.platform === 'facebook' ? 'border-blue-200 bg-blue-50' :
                task.platform === 'tiktok' ? 'border-gray-200 bg-gray-50' :
                'border-purple-200 bg-purple-50'
              }`}>
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">{task.title}</span>
                  <span className={`inline-flex items-center px-2 py-1 rounded text-xs ${
                    task.status === 'completed' ? 'bg-green-100 text-green-800' :
                    task.status === 'in_progress' ? 'bg-yellow-100 text-yellow-800' :
                    'bg-red-100 text-red-800'
                  }`}>
                    {task.status}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{task.platform}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Tools Quick Access */}
      <div className="bg-white shadow rounded-lg">
        <div className="px-4 py-5 sm:p-6">
          <h3 className="text-lg leading-6 font-medium text-gray-900 mb-4">
            AI Content Tools
          </h3>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <button className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
              <Hash className="h-6 w-6 text-indigo-600 mr-3" />
              <div className="text-left">
                <p className="text-sm font-medium text-gray-900">Hashtag Generator</p>
                <p className="text-sm text-gray-500">AI-powered hashtags</p>
              </div>
            </button>
            <button className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
              <Image className="h-6 w-6 text-indigo-600 mr-3" />
              <div className="text-left">
                <p className="text-sm font-medium text-gray-900">Image Ideas</p>
                <p className="text-sm text-gray-500">Visual content suggestions</p>
              </div>
            </button>
            <button className="flex items-center p-4 border border-gray-200 rounded-lg hover:bg-gray-50">
              <Zap className="h-6 w-6 text-indigo-600 mr-3" />
              <div className="text-left">
                <p className="text-sm font-medium text-gray-900">AI Writer</p>
                <p className="text-sm text-gray-500">Generate captions & content</p>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Create Task Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-gray-600 bg-opacity-50 overflow-y-auto h-full w-full">
          <div className="relative top-20 mx-auto p-5 border w-96 shadow-lg rounded-md bg-white">
            <div className="mt-3">
              <h3 className="text-lg font-medium text-gray-900 mb-4">Create Content Task</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700">Title</label>
                  <input
                    type="text"
                    value={newTask.title}
                    onChange={(e) => setNewTask({...newTask, title: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Type</label>
                    <select
                      value={newTask.type}
                      onChange={(e) => setNewTask({...newTask, type: e.target.value})}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    >
                      <option value="post">Social Post</option>
                      <option value="story">Story</option>
                      <option value="reel">Reel/Video</option>
                      <option value="blog">Blog Post</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700">Platform</label>
                    <select
                      value={newTask.platform}
                      onChange={(e) => setNewTask({...newTask, platform: e.target.value})}
                      className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                    >
                      <option value="instagram">Instagram</option>
                      <option value="facebook">Facebook</option>
                      <option value="tiktok">TikTok</option>
                      <option value="twitter">Twitter</option>
                      <option value="youtube">YouTube</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">Due Date</label>
                  <input
                    type="date"
                    value={newTask.due_date}
                    onChange={(e) => setNewTask({...newTask, due_date: e.target.value})}
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700">
                    Description
                    <button
                      type="button"
                      onClick={generateAIContent}
                      className="ml-2 inline-flex items-center px-2 py-1 border border-transparent text-xs font-medium rounded text-indigo-700 bg-indigo-100 hover:bg-indigo-200"
                    >
                      <Zap className="h-3 w-3 mr-1" />
                      AI Generate
                    </button>
                  </label>
                  <textarea
                    value={newTask.description}
                    onChange={(e) => setNewTask({...newTask, description: e.target.value})}
                    rows="3"
                    className="mt-1 block w-full border border-gray-300 rounded-md shadow-sm p-2"
                  />
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-4">
                <button
                  onClick={() => setShowCreateModal(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 hover:text-gray-500"
                >
                  Cancel
                </button>
                <button
                  onClick={createTask}
                  className="px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-md hover:bg-indigo-700"
                >
                  Create Task
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default ContentManager