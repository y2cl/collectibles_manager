import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import styles from './Layout.module.css';
import { useTheme } from '../../hooks/useTheme';

export default function Layout() {
  useTheme(); // applies appearance store → CSS custom properties on every render
  return (
    <div className={styles.shell}>
      <Sidebar />
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  );
}
