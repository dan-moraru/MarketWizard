import './App.css';
import ProjectHeader from "./ProjectHeader";
import Footer from './Footer.jsx';
import Dashboard from './dashboard.jsx';

function App() {
  return (
    <div className="App">
      <ProjectHeader />
      <Dashboard/>
      <Footer />
    </div>
  );
}

export default App;
