import './App.css';
import ProjectHeader from "./ProjectHeader";
import Footer from './Footer.jsx';
import Dashboard from './dashboard.jsx';
import Intro from './Intro.jsx';

function App() {
  return (
    <div className="App">
      <div className="main-content">
        <ProjectHeader />
        <Intro />
        <Dashboard />
      </div>
      <Footer />
    </div>
  );
}


export default App;
