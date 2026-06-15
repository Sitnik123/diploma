import math

class DeepfakeVulnerabilityScorer:
    """
    Расчет индекса уязвимости к дипфейкам (DFVS)
    """
    
    WEIGHTS = {
        'quantity': 0.35,
        'quality': 0.25,
        'diversity': 0.20,
        'social': 0.10,
        'fame': 0.10
    }
    
    SOCIAL_WEIGHTS = {
        'президент': 10.0, 'директор': 9.0, 'генеральный': 9.5,
        'певец': 9.0, 'певица': 9.0, 'модель': 8.5,
        'футболист': 8.0, 'бизнесмен': 7.5, 'менеджер': 5.0,
        'банковский': 6.0, 'фармацевт': 4.0, 'студент': 3.0,
        'сотрудник': 2.0
    }
    
    FAMOUS_PEOPLE = [
        'илон маск', 'elon musk', 'джастин бибер', 'justin bieber',
        'владимир путин', 'putin', 'дональд трамп', 'trump'
    ]
    
    def calc_quantity_score(self, photo_count: int) -> float:
        if photo_count <= 0:
            return 0.0
        score = 2 + 3 * math.log10(photo_count + 1)
        return round(min(10.0, score), 2)
    
    def calc_quality_score(self, quality_metrics: dict) -> float:
        overall = quality_metrics.get('overall_score', 0.5)
        return round(overall * 10, 2)
    
    def calc_diversity_score(self, sources: list) -> float:
        if not sources:
            return 0.0
        domains = set()
        for src in sources:
            domain = src.get('source', '')
            if domain and domain != 'unknown':
                domains.add(domain)
        score = min(10.0, 2 + len(domains) * 1.5)
        return round(score, 2)
    
    def calc_social_score(self, position: str) -> float:
        position_lower = position.lower()
        for key, weight in self.SOCIAL_WEIGHTS.items():
            if key in position_lower:
                return weight
        return 2.0
    
    def calc_fame_bonus(self, name: str) -> float:
        name_lower = name.lower()
        for famous in self.FAMOUS_PEOPLE:
            if famous in name_lower:
                return 3.0
        return 0.0
    
    def calculate_dfvs(self, photo_count: int, quality_metrics: dict,
                      sources: list, position: str, name: str = '') -> dict:
        
        qnt = self.calc_quantity_score(photo_count)
        qlt = self.calc_quality_score(quality_metrics)
        div = self.calc_diversity_score(sources)
        soc = self.calc_social_score(position)
        fame = self.calc_fame_bonus(name)
        
        raw = (qnt * self.WEIGHTS['quantity'] +
               qlt * self.WEIGHTS['quality'] +
               div * self.WEIGHTS['diversity'] +
               soc * self.WEIGHTS['social'] +
               fame * self.WEIGHTS['fame'])
        
        if fame > 0:
            raw = max(raw, 7.5)
        
        final = round(min(10.0, raw), 2)
        
        if final >= 8.0:
            risk = 'КРИТИЧЕСКИЙ'
            rec = f"КРИТИЧЕСКАЯ УЯЗВИМОСТЬ: Найдено {photo_count} фото. Немедленно удалите публичные фото!"
        elif final >= 6.0:
            risk = 'ВЫСОКИЙ'
            rec = f"ВЫСОКИЙ РИСК: Найдено {photo_count} фото. Настройте приватность соцсетей."
        elif final >= 4.0:
            risk = 'СРЕДНИЙ'
            rec = f"СРЕДНИЙ РИСК: Найдено {photo_count} фото. Проверьте настройки приватности."
        else:
            risk = 'НИЗКИЙ'
            rec = f"НИЗКИЙ РИСК: Найдено {photo_count} фото. Уровень безопасности хороший."
        
        return {
            'dfvs_score': final,
            'risk_level': risk,
            'recommendation': rec,
            'components': {
                'quantity': qnt,
                'quality': qlt,
                'diversity': div,
                'social': soc,
                'fame_bonus': fame
            }
        }
